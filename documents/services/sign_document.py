import base64
import io
import os
from io import BytesIO
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pdf2image import convert_from_bytes

from documents.models import DocumentAttachment

class SignatureAgent:
    """
    A class to handle document signing with base64-encoded signatures and comments.
    Supports both PDF and image documents.
    """
    
    # Supported image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    
    def __init__(self, signature_model):
        """
        Initialize the SignatureAgent with a Signature model instance.
        
        Args:
            signature_model: An instance of the Signature model containing:
                - signature: base64-encoded signature image
                - attachment: ForeignKey to DocumentAttachment
        """
        self.signature_model = signature_model
        self.signature_image = None
        self.document = signature_model.attachment.document
        self.comments = self.document.comments if hasattr(self.document, 'comments') else ""
        
    def _decode_signature(self):
        """Decode the base64 signature into a PIL Image."""
        try:
            # Remove the data URL prefix if present
            if 'base64,' in self.signature_model.signature_data:
                base64_str = self.signature_model.signature_data.split('base64,')[1]
            else:
                base64_str = self.signature_model.signature_data
                
            # Decode base64 to bytes and create PIL Image
            signature_data = base64.b64decode(base64_str)
            self.signature_image = Image.open(BytesIO(signature_data)).convert('RGBA')
            return True
        except Exception as e:
            raise ValueError(f"Failed to decode signature: {str(e)}")
    
    def _get_file_extension(self, filename):
        """Get the lowercase file extension."""
        return Path(filename).suffix.lower()
    
    def _is_pdf(self, filename):
        """Check if the file is a PDF."""
        return self._get_file_extension(filename) == '.pdf'
    
    def _is_image(self, filename):
        """Check if the file is a supported image format."""
        return self._get_file_extension(filename) in self.IMAGE_EXTENSIONS
    
    def _resize_signature(self, target_width):
        """Resize the signature to fit the target width while maintaining aspect ratio."""
        if not self.signature_image:
            return False
            
        # Calculate new size (30% of target width, maintaining aspect ratio)
        target_width = int(target_width * 0.3)
        aspect_ratio = self.signature_image.width / self.signature_image.height
        new_height = int(target_width / aspect_ratio)
        
        # Resize the signature
        self.signature_image = self.signature_image.resize(
            (target_width, new_height),
            Image.Resampling.LANCZOS
        )
        return True
    
    def _format_arabic_text(self, text):
        """Format Arabic text to display correctly (right-to-left)."""
        try:
            # Check if text contains Arabic characters
            if any('\u0600' <= char <= '\u06FF' for char in text):
                # Reshape Arabic text and apply bidirectional algorithm
                reshaped_text = arabic_reshaper.reshape(text)
                bidi_text = get_display(reshaped_text)
                return bidi_text
            return text
        except Exception:
            # If Arabic processing fails, return original text
            return text
    
    def _add_signature_to_pdf(self, pdf_bytes):
        """Add signature and comments to a PDF document while preserving original page size and orientation."""
        try:
            # Open the original PDF to detect page sizes and orientations
            original_pdf = PdfReader(BytesIO(pdf_bytes))
            page_sizes = []
            page_orientations = []
            
            # Detect page sizes and orientations for all pages
            for page in original_pdf.pages:
                # Get page dimensions in points (72 DPI)
                media_box = page.mediabox
                width = float(media_box.width)
                height = float(media_box.height)
                
                # Store original dimensions
                page_sizes.append((width, height))
                
                # Determine orientation (width > height = landscape, otherwise portrait)
                orientation = "landscape" if width > height else "portrait"
                page_orientations.append(orientation)
                
            # Get first page dimensions
            first_page_width, first_page_height = page_sizes[0]
            first_page_orientation = page_orientations[0]
            
            # Convert first page to image with fixed DPI for consistent sizing
            images = convert_from_bytes(pdf_bytes, first_page=1, last_page=1, dpi=150)
            if not images:
                raise ValueError("Failed to convert PDF to image")
                
            first_page_img = images[0]
            
            # Calculate dimensions in pixels at 150 DPI
            width_px = int(first_page_width * 150 / 72)
            height_px = int(first_page_height * 150 / 72)
            
            # Ensure image matches original page dimensions
            if first_page_img.size != (width_px, height_px):
                # Resize the image to match original dimensions while maintaining aspect ratio
                first_page_img = first_page_img.resize((width_px, height_px), Image.Resampling.LANCZOS)
            
            # Resize signature to fit the page
            self._resize_signature(first_page_img.width)
            
            # Create a drawing context
            draw = ImageDraw.Draw(first_page_img)
            
            # Calculate positions for signature and comments side by side at 50px from bottom
            bottom_margin = 50
            base_y = first_page_img.height - bottom_margin
            
            # Determine the layout based on what we have
            signature_width = self.signature_image.width if self.signature_image else 0
            
            # Prepare comments text and calculate dimensions
            comments_lines = []
            comments_width = 0
            comments_height = 0
            font = None
            
            if self.comments:
                # Use bold font with 18pt size for better visibility
                try:
                    font = ImageFont.truetype("arialbd.ttf", 18)  # Arial Bold
                except IOError:
                    try:
                        font = ImageFont.truetype("arial.ttf", 18)  # Fallback to regular Arial
                    except IOError:
                        font = ImageFont.load_default()
                
                # Format Arabic text properly
                formatted_comments = self._format_arabic_text(self.comments)
                comments_lines = [line for line in formatted_comments.split('\n') if line.strip()]
                
                # Calculate comments dimensions
                for line in comments_lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    comments_width = max(comments_width, line_width)
                
                comments_height = len(comments_lines) * 25  # 20px per line
            
            # Calculate total width and spacing
            spacing = 30  # Space between signature and comments
            total_width = signature_width + (spacing if signature_width > 0 and comments_width > 0 else 0) + comments_width
            
            # Default to bottom-right corner for signature positioning
            # Calculate margin from right edge (50px)
            right_margin = 50
            
            # Add signature
            if self.signature_image:
                # Position signature at bottom-right corner
                signature_x = first_page_img.width - self.signature_image.width - right_margin
                signature_y = base_y - self.signature_image.height
                
                # Ensure signature has transparency
                if self.signature_image.mode != 'RGBA':
                    self.signature_image = self.signature_image.convert('RGBA')
                
                # Paste signature with transparency
                first_page_img.paste(
                    self.signature_image,
                    (signature_x, signature_y),
                    self.signature_image  # Use the image itself as mask to preserve transparency
                )
            
            # Add comments to the left of signature
            if self.comments and comments_lines:
                # Position comments to the left of the signature
                comments_x = signature_x - comments_width - spacing if self.signature_image else first_page_img.width - comments_width - right_margin
                comments_y = base_y - comments_height
                
                # Draw each line of comments (right-aligned)
                y_text = comments_y
                for line in comments_lines:
                    # Calculate line width for right alignment
                    bbox = draw.textbbox((0, 0), line, font=font)
                    line_width = bbox[2] - bbox[0]
                    # Right-align by positioning at comments_x + comments_width - line_width
                    x_text = comments_x + comments_width - line_width
                    draw.text((x_text, y_text), line, fill="black", font=font)
                    y_text += 25  # Move down for next line
            
            # Convert back to PDF with original page dimensions
            from reportlab.pdfgen import canvas
            from reportlab.lib.utils import ImageReader
            
            # Create a temporary PDF with original page size
            temp_pdf = BytesIO()
            c = canvas.Canvas(temp_pdf, pagesize=(first_page_width, first_page_height))
            
            # Convert PIL Image to ImageReader for ReportLab
            img_reader = ImageReader(first_page_img)
            
            # Draw the image on canvas with original dimensions
            c.drawImage(img_reader, 0, 0, width=first_page_width, height=first_page_height, preserveAspectRatio=True)
            c.save()
            
            # Merge with remaining pages
            original_pdf = PdfReader(BytesIO(pdf_bytes))
            output = PdfWriter()
            
            # Add modified first page with original size and orientation preserved
            temp_pdf.seek(0)
            modified_first_page = PdfReader(temp_pdf)
            output.add_page(modified_first_page.pages[0])
            
            # Add remaining pages
            for page_num in range(1, len(original_pdf.pages)):
                output.add_page(original_pdf.pages[page_num])
            
            # Save to bytes
            output_stream = BytesIO()
            output.write(output_stream)
            return output_stream.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to process PDF: {str(e)}")
    
    def _add_signature_to_image(self, image_bytes):
        """Add signature and comments to an image."""
        try:
            # Open the image
            img = Image.open(BytesIO(image_bytes)).convert('RGBA')
            
            # Resize signature to fit the image
            self._resize_signature(img.width)
            
            # Create a drawing context
            draw = ImageDraw.Draw(img)
            
            # Add signature (bottom center)
            signature_y = None
            if self.signature_image:
                x = (img.width - self.signature_image.width) // 2
                y = img.height - self.signature_image.height - 80  # 80px from bottom to leave space for comments
                signature_y = y + self.signature_image.height  # Bottom of signature
                
                # Paste signature with transparency
                img.paste(
                    self.signature_image,
                    (x, y),
                    self.signature_image
                )
            
            # Add comments (below signature, centered)
            if self.comments:
                try:
                    font = ImageFont.truetype("arial.ttf", 24)  # Larger font for images
                except IOError:
                    font = ImageFont.load_default()
                
                # Format Arabic text properly
                formatted_comments = self._format_arabic_text(self.comments)
                
                # Split comments into lines and add below signature
                lines = formatted_comments.split('\n')
                y_text = signature_y + 15 if signature_y else img.height - 60  # 15px below signature or 60px from bottom
                
                for line in lines:
                    if line.strip():  # Only draw non-empty lines
                        # Get text dimensions for centering
                        bbox = draw.textbbox((0, 0), line, font=font)
                        text_width = bbox[2] - bbox[0]
                        x_text = (img.width - text_width) // 2  # Center horizontally
                        
                        draw.text((x_text, y_text), line, fill="black", font=font)
                        y_text += 35  # More spacing for images
            
            # Convert back to bytes
            output = BytesIO()
            img_format = 'PNG' if img.mode == 'RGBA' else 'JPEG'
            img.save(output, format=img_format)
            return output.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to process image: {str(e)}")
    
    def process_document(self):
        """
        Process the document by adding the signature and comments.
        
        Returns:
            ContentFile: The processed document ready to be saved.
        """
        if not self.signature_model.attachment.file:
            raise ValueError("No document attachment found")
        
        # Decode the signature
        self._decode_signature()
        
        # Read the document file
        document_file = self.signature_model.attachment.file
        file_extension = self._get_file_extension(document_file.name)
        
        try:
            with document_file.open('rb') as f:
                file_content = f.read()
            
            # Process based on file type
            if self._is_pdf(document_file.name):
                processed_content = self._add_signature_to_pdf(file_content)
                content_type = 'application/pdf'
                file_extension = '.pdf'
            elif self._is_image(document_file.name):
                processed_content = self._add_signature_to_image(file_content)
                content_type = f'image/{file_extension[1:]}'  # remove the dot
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")
            
            # Create a ContentFile with the processed content
            file_like_obj = ContentFile(processed_content, name=f"signed_{document_file.name}")
            self.signature_model.attachment.file = file_like_obj
            self.signature_model.attachment.save()
            self.document.status = 'signed'
            self.document.save()
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to process document: {str(e)}")

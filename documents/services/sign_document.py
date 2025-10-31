import base64
from io import BytesIO
from pathlib import Path
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import datetime

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from pdf2image import convert_from_bytes

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
                - signature_data: base64-encoded signature drawing image
                - comments_data: base64-encoded comments text image
                - attachment: ForeignKey to DocumentAttachment
        """
        self.signature_model = signature_model
        self.signature_image = None
        self.comments_image = None
        self.document = signature_model.attachment.document

    def _decode_signature(self):
        """Decode the base64 signature into a PIL Image."""
        try:
            if not self.signature_model.signature_data:
                self.signature_image = None
                return True

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

    def _decode_comments(self):
        """Decode the base64 comments into a PIL Image."""
        try:
            if not self.signature_model.comments_data:
                self.comments_image = None
                return True

            # Remove the data URL prefix if present
            if 'base64,' in self.signature_model.comments_data:
                base64_str = self.signature_model.comments_data.split('base64,')[1]
            else:
                base64_str = self.signature_model.comments_data

            # Decode base64 to bytes and create PIL Image
            comments_data = base64.b64decode(base64_str)
            self.comments_image = Image.open(BytesIO(comments_data)).convert('RGBA')
            return True
        except Exception as e:
            raise ValueError(f"Failed to decode comments: {str(e)}")
    
    def _get_file_extension(self, filename):
        """Get the lowercase file extension."""
        return Path(filename).suffix.lower()
    
    def _is_pdf(self, filename):
        """Check if the file is a PDF."""
        return self._get_file_extension(filename) == '.pdf'
    
    def _is_image(self, filename):
        """Check if the file is a supported image format."""
        return self._get_file_extension(filename) in self.IMAGE_EXTENSIONS
    
    def _resize_image(self, image, target_width, scale_factor=0.3):
        """Resize an image to fit the target width while maintaining aspect ratio."""
        if not image:
            return None

        # Calculate new size (scale_factor of target width, maintaining aspect ratio)
        new_width = int(target_width * scale_factor)
        aspect_ratio = image.width / image.height
        new_height = int(new_width / aspect_ratio)

        # Resize the image
        resized = image.resize(
            (new_width, new_height),
            Image.Resampling.LANCZOS
        )
        return resized
    
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

            # Resize signature and comments images to fit the page
            resized_signature = self._resize_image(self.signature_image, first_page_img.width, scale_factor=0.25)
            resized_comments = self._resize_image(self.comments_image, first_page_img.width, scale_factor=0.5)  # Increased from 0.35 to 0.5

            # Calculate positions with bottom margin
            bottom_margin = 250  # Margin from bottom
            left_margin = 60    # Margin from left for signature

            # Position signature at bottom left
            if resized_signature:
                signature_x = left_margin
                signature_y = first_page_img.height - bottom_margin - resized_signature.height

                # Ensure signature has transparency
                if resized_signature.mode != 'RGBA':
                    resized_signature = resized_signature.convert('RGBA')

                # Paste signature with transparency
                first_page_img.paste(
                    resized_signature,
                    (signature_x, signature_y),
                    resized_signature  # Use the image itself as mask to preserve transparency
                )

            # Position comments at bottom right
            if resized_comments:
                # Ensure comments has transparency before rotation
                if resized_comments.mode != 'RGBA':
                    resized_comments = resized_comments.convert('RGBA')

                # Rotate comments image by 20 degrees
                resized_comments = resized_comments.rotate(20, expand=True, resample=Image.Resampling.BICUBIC)

                # Adjust position: move right and up
                x_offset = 30  # Move more to the right
                y_offset = -20  # Move up
                comments_x = left_margin + resized_signature.width + x_offset
                comments_y = first_page_img.height - bottom_margin - resized_signature.height + y_offset

                # Paste comments with transparency
                first_page_img.paste(
                    resized_comments,
                    (comments_x, comments_y),
                    resized_comments  # Use the image itself as mask to preserve transparency
                )
            
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
            # Open the image and preserve original format and orientation
            img = Image.open(BytesIO(image_bytes))
            original_mode = img.mode
            original_format = img.format

            # Preserve EXIF data to maintain orientation
            exif_dict = img.getexif() if hasattr(img, 'getexif') else None

            # Convert to RGBA for transparency support during processing
            if original_mode != 'RGBA':
                img = img.convert('RGBA')

            # Resize signature and comments images to fit the page
            resized_signature = self._resize_image(self.signature_image, img.width, scale_factor=0.25)
            resized_comments = self._resize_image(self.comments_image, img.width, scale_factor=0.5)  # Increased from 0.35 to 0.5

            # Calculate positions with bottom margin
            bottom_margin = 250  # Margin from bottom
            left_margin = 60    # Margin from left for signature

            # Position signature at bottom left
            if resized_signature:
                signature_x = left_margin
                signature_y = img.height - bottom_margin - resized_signature.height

                # Ensure signature has transparency
                if resized_signature.mode != 'RGBA':
                    resized_signature = resized_signature.convert('RGBA')

                # Paste signature with transparency
                img.paste(
                    resized_signature,
                    (signature_x, signature_y),
                    resized_signature
                )

            # Position comments next to signature (same as PDF positioning)
            if resized_comments:
                # Ensure comments has transparency before rotation
                if resized_comments.mode != 'RGBA':
                    resized_comments = resized_comments.convert('RGBA')

                # Rotate comments image by 20 degrees
                resized_comments = resized_comments.rotate(20, expand=True, resample=Image.Resampling.BICUBIC)

                # Adjust position: move right and up
                x_offset = 30  # Move more to the right
                y_offset = -20  # Move up
                comments_x = left_margin + resized_signature.width + x_offset
                comments_y = img.height - bottom_margin - resized_signature.height + y_offset

                # Paste comments with transparency
                img.paste(
                    resized_comments,
                    (comments_x, comments_y),
                    resized_comments
                )
            
            # Convert back to original format to preserve orientation
            output = BytesIO()

            # Convert back to original mode if it was changed
            if original_mode != 'RGBA' and img.mode == 'RGBA':
                if original_mode == 'RGB':
                    img = img.convert('RGB')
                elif original_mode == 'L':
                    img = img.convert('L')
                elif original_mode == 'P':
                    img = img.convert('P')

            # Determine format - preserve original format if possible
            if original_format and original_format in ['JPEG', 'PNG', 'BMP', 'GIF', 'TIFF']:
                img_format = original_format
            else:
                img_format = 'PNG' if img.mode == 'RGBA' else 'JPEG'

            # Save with preserved EXIF data if available
            save_kwargs = {'format': img_format}
            if exif_dict and img_format in ['JPEG', 'TIFF']:
                save_kwargs['exif'] = exif_dict

            img.save(output, **save_kwargs)
            return output.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to process image: {str(e)}")
    
    def process_document(self):
        """
        Process the document by adding the signature and comments.
        For images, signs ALL related attachments.
        For PDFs, signs only the specific attachment.

        Returns:
            Boolean: True if processing was successful.
        """
        if not self.signature_model.attachment.file:
            raise ValueError("No document attachment found")

        # Decode both signature and comments images
        self._decode_signature()
        self._decode_comments()

        # Check if this is an image document
        document_file = self.signature_model.attachment.file
        file_extension = self._get_file_extension(document_file.name)

        try:
            if self._is_pdf(document_file.name):
                # For PDFs, process only the specific attachment
                self._process_single_attachment(self.signature_model.attachment)
            elif self._is_image(document_file.name):
                # For images, process ALL attachments related to this document
                all_attachments = self.document.attachments.all()
                for attachment in all_attachments:
                    if self._is_image(attachment.file.name):
                        self._process_single_attachment(attachment)
            else:
                raise ValueError(f"Unsupported file format: {file_extension}")

            # Update document status to signed
            self.document.status = 'signed'
            self.document.save()

            return True

        except Exception as e:
            raise Exception(f"Failed to process document: {str(e)}")

    def _process_single_attachment(self, attachment):
        """
        Process a single attachment by adding signature and comments.

        Args:
            attachment: DocumentAttachment instance to process
        """
        with attachment.file.open('rb') as f:
            file_content = f.read()

        file_extension = self._get_file_extension(attachment.file.name)

        # Process based on file type
        if self._is_pdf(attachment.file.name):
            processed_content = self._add_signature_to_pdf(file_content)
        elif self._is_image(attachment.file.name):
            processed_content = self._add_signature_to_image(file_content)
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")

        # Create a ContentFile with the processed content
        timestamp = int(datetime.now().timestamp())
        filename = f"signed_{timestamp}{file_extension}"
        file_like_obj = ContentFile(processed_content, name=filename)
        attachment.file = file_like_obj
        attachment.is_signed = True
        attachment.save()

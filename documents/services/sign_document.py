import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple, List, Dict

from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
import arabic_reshaper
from bidi.algorithm import get_display
from django.core.files.base import ContentFile
from pdf2image import convert_from_bytes


class SignatureAgent:
    """
    A clean, refactored class for handling document signing with signatures, comments, and department lists.
    Supports PDF and image documents with proper RTL Arabic text handling.
    """
    
    # Supported image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    
    # Configuration - positions as percentages of document dimensions (0.0 to 1.0)
    SIGNATURE_HORIZONTAL_POSITION = 0.85  # 85% from left (right-aligned)
    SIGNATURE_VERTICAL_POSITION = 0.90    # 95% from top (bottom-aligned)
    ELEMENTS_MIN_MARGIN = 0.02            # 2% minimum margin from edges
    
    # Side-by-side elements configuration
    SIDE_BY_SIDE_GAP_PIXELS = 10          # Gap between department list and comments
    SIDE_BY_SIDE_MAX_WIDTH_RATIO = 0.5    # Combined elements max width is 50% of page
    
    # Department list styling
    DEPARTMENT_FONT_SIZE = 20
    DEPARTMENT_BULLET = '•'
    DEPARTMENT_COLOR = (255, 0, 0, 255)  # Red color with alpha
    DEPARTMENT_LINE_SPACING = 5
    DEPARTMENT_PADDING = 1
    
    # Element scaling factors (relative to document width)
    # Smaller signature to avoid covering document content
    SIGNATURE_SCALE_FACTOR = 0.12
    COMMENTS_SCALE_FACTOR = 0.35
    DEPARTMENT_SCALE_FACTOR = 0.25
    
    def __init__(self, signature_model):
        """
        Initialize the SignatureAgent with a Signature model instance.
        
        Args:
            signature_model: Signature model instance containing:
                - signature_data: base64 signature image
                - comments_data: base64 comments image
                - department_list: list of department names
                - attachment: ForeignKey to DocumentAttachment
        """
        self.signature_model = signature_model
        self.signature_image: Optional[Image.Image] = None
        self.comments_image: Optional[Image.Image] = None
        self.document = signature_model.attachment.document
    
    # ==================== UTILITY METHODS ====================
    
    @staticmethod
    def _validate_percentage(value: float, name: str = 'percentage') -> float:
        """Validate that a percentage value is between 0.0 and 1.0."""
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")
        return float(value)
    
    @staticmethod
    def _calculate_position_from_edge(
        document_dimension: int,
        element_dimension: int,
        percentage: float,
        margin_percentage: float = 0.02,
        from_bottom_or_right: bool = False
    ) -> int:
        """
        Calculate position from edge with margin constraints.
        
        Args:
            document_dimension: Document width or height in pixels
            element_dimension: Element width or height in pixels
            percentage: Position as percentage from edge (0.0-1.0)
            margin_percentage: Minimum margin as percentage
            from_bottom_or_right: If True, calculate from bottom/right edge
        
        Returns:
            Absolute position in pixels
        """
        percentage = SignatureAgent._validate_percentage(percentage, 'percentage')
        margin_percentage = SignatureAgent._validate_percentage(margin_percentage, 'margin_percentage')
        
        margin_pixels = int(document_dimension * margin_percentage)
        
        if from_bottom_or_right:
            # Position from bottom/right edge
            position_from_edge = document_dimension * percentage
            position = position_from_edge - element_dimension
            max_position = document_dimension - element_dimension - margin_pixels
        else:
            # Position from top/left edge
            position = document_dimension * percentage
            max_position = document_dimension - element_dimension - margin_pixels
        
        min_position = margin_pixels
        return int(max(min_position, min(position, max_position)))
    
    @staticmethod
    def _get_arabic_font(font_size: int) -> ImageFont.FreeTypeFont:
        """Try to load a font that supports Arabic characters."""
        font_candidates = [
            # Arabic-supporting fonts
            "arial.ttf",
            "Arial.ttf",
            "tahoma.ttf",
            "Tahoma.ttf",
            "times.ttf",
            "Times.ttf",
            "DejaVuSans.ttf",
            "LiberationSans-Regular.ttf",
        ]
        
        # Common font paths
        paths_to_try = []
        
        # Windows
        if Path("C:/").exists():
            paths_to_try.extend([
                "C:/Windows/Fonts/",
                "C:/WINNT/Fonts/",
            ])
        
        # Linux/Mac
        paths_to_try.extend([
            "/usr/share/fonts/truetype/",
            "/usr/share/fonts/TTF/",
            "/Library/Fonts/",
            "/System/Library/Fonts/",
        ])
        
        for base_path in paths_to_try:
            for font_name in font_candidates:
                font_path = Path(base_path) / font_name
                if font_path.exists():
                    try:
                        return ImageFont.truetype(str(font_path), font_size)
                    except Exception:
                        continue
        
        # Fallback to default
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except:
            return ImageFont.load_default()
    
    @staticmethod
    def _format_text_for_display(text: str) -> str:
        """
        Format text for proper display, handling Arabic RTL text correctly.
        
        Args:
            text: Input text that may contain Arabic
            
        Returns:
            Properly formatted text for display
        """
        if not text:
            return ""
        
        # Check if text contains Arabic characters
        has_arabic = any('\u0600' <= char <= '\u06FF' for char in text)
        
        if has_arabic:
            try:
                # Reshape and apply bidirectional algorithm for Arabic
                reshaped = arabic_reshaper.reshape(text)
                formatted = get_display(reshaped)
                return formatted
            except Exception:
                # If Arabic processing fails, return original
                return text
        
        return text
    
    # ==================== IMAGE DECODING ====================
    
    def _decode_base64_image(self, base64_data: str) -> Optional[Image.Image]:
        """Decode base64 string into PIL Image."""
        if not base64_data or not base64_data.strip():
            return None
        
        try:
            # Extract base64 string from data URL if present
            if 'base64,' in base64_data:
                base64_str = base64_data.split('base64,')[1]
            else:
                base64_str = base64_data
            
            if not base64_str.strip():
                return None
            
            # Decode base64
            image_data = base64.b64decode(base64_str)
            image = Image.open(BytesIO(image_data))
            
            # Convert to RGBA for transparency support
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            return image
            
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image: {str(e)}")
    
    def _decode_signature(self):
        """Decode signature image from base64."""
        if hasattr(self.signature_model, 'signature_data'):
            self.signature_image = self._decode_base64_image(self.signature_model.signature_data)
    
    def _decode_comments(self):
        """Decode comments image from base64."""
        if hasattr(self.signature_model, 'comments_data'):
            self.comments_image = self._decode_base64_image(self.signature_model.comments_data)
    
    # ==================== DEPARTMENT LIST RENDERING ====================
    
    def _get_department_list(self) -> List[str]:
        """Extract and normalize department list from model."""
        if not hasattr(self.signature_model, 'department_list'):
            return []
        
        dept_list = self.signature_model.department_list
        if not dept_list:
            return []
        
        # Handle different data types
        if isinstance(dept_list, list):
            return [str(item).strip() for item in dept_list if str(item).strip()]
        elif isinstance(dept_list, str):
            # Try to parse as comma-separated list
            return [item.strip() for item in dept_list.split(',') if item.strip()]
        
        return []
    
    def _render_department_list(self, max_width_px: int) -> Optional[Image.Image]:
        """
        Render department list as a transparent bulleted list image.
        
        Args:
            max_width_px: Maximum width for the department list
            
        Returns:
            PIL Image with transparent background, or None if no departments
        """
        departments = self._get_department_list()
        if not departments:
            return None
        
        font = self._get_arabic_font(self.DEPARTMENT_FONT_SIZE)
        
        # Temporary image for text measurement
        temp_img = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        
        # Measure bullet size
        bullet_w, bullet_h = temp_draw.textbbox((0, 0), self.DEPARTMENT_BULLET, font=font)[2:4]
        bullet_gap = 8
        bullet_area = bullet_w + bullet_gap
        
        def measure_text(text: str) -> Tuple[int, int]:
            """Measure text dimensions."""
            bbox = temp_draw.textbbox((0, 0), text, font=font)
            return bbox[2] - bbox[0], bbox[3] - bbox[1]
        
        # Process and wrap department names
        # lines_to_render: List of (text, is_arabic, is_first_line_of_department)
        lines_to_render = []
        
        for dept in departments:
            dept = dept.strip()
            if not dept:
                continue
            
            # Check if text contains Arabic
            is_arabic = any('\u0600' <= ch <= '\u06FF' for ch in dept)
            
            # Format text for display
            display_text = self._format_text_for_display(dept) if is_arabic else dept
            
            # Maximum text width (accounting for bullet)
            text_max_width = max_width_px - (self.DEPARTMENT_PADDING * 2)
            if is_arabic:
                text_max_width -= bullet_area  # Reserve space for bullet on right
            
            # Simple word wrapping
            words = display_text.split()
            current_line = ""
            is_first_line_of_dept = True
            
            for word in words:
                test_line = f"{current_line} {word}" if current_line else word
                line_w, _ = measure_text(test_line)
                
                if line_w <= text_max_width:
                    current_line = test_line
                else:
                    if current_line:
                        lines_to_render.append((current_line, is_arabic, is_first_line_of_dept))
                        is_first_line_of_dept = False
                    current_line = word
            
            if current_line:
                lines_to_render.append((current_line, is_arabic, is_first_line_of_dept))
        
        if not lines_to_render:
            return None
        
        # Calculate total dimensions
        line_heights = []
        line_widths = []
        
        for text, is_arabic, is_first in lines_to_render:
            w, h = measure_text(text)
            line_widths.append(w)
            line_heights.append(h)
        
        max_line_width = max(line_widths)
        total_height = sum(line_heights) + (self.DEPARTMENT_LINE_SPACING * (len(lines_to_render) - 1))
        
        # Create final image
        img_width = min(max_width_px, max_line_width + bullet_area + (self.DEPARTMENT_PADDING * 2))
        img_height = total_height + (self.DEPARTMENT_PADDING * 2)
        
        result_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(result_img)
        
        # Draw each line
        y = self.DEPARTMENT_PADDING
        
        for i, (text, is_arabic, is_first) in enumerate(lines_to_render):
            line_w, line_h = measure_text(text)
            
            if is_arabic:
                # Arabic/RTL: bullet on right, text right-aligned
                bullet_x = img_width - self.DEPARTMENT_PADDING - bullet_w
                if is_first:  # Only draw bullet on first line of department
                    draw.text((bullet_x, y), self.DEPARTMENT_BULLET, font=font, fill=self.DEPARTMENT_COLOR)
                
                text_x = img_width - self.DEPARTMENT_PADDING - bullet_area - line_w
                draw.text((text_x, y), text, font=font, fill=self.DEPARTMENT_COLOR)
            else:
                # LTR: bullet on left
                if is_first:  # Only draw bullet on first line of department
                    draw.text((self.DEPARTMENT_PADDING, y), self.DEPARTMENT_BULLET, font=font, fill=self.DEPARTMENT_COLOR)
                
                text_x = self.DEPARTMENT_PADDING + bullet_area
                draw.text((text_x, y), text, font=font, fill=self.DEPARTMENT_COLOR)
            
            y += line_h + self.DEPARTMENT_LINE_SPACING
        
        return result_img
    
    # ==================== IMAGE RESIZING ====================
    
    @staticmethod
    def _resize_to_width(image: Image.Image, target_width: int, maintain_aspect: bool = True) -> Image.Image:
        """Resize image to target width while maintaining aspect ratio."""
        if not image or target_width <= 0:
            return image
        
        if image.width <= target_width:
            return image
        
        if maintain_aspect:
            ratio = target_width / image.width
            target_height = int(image.height * ratio)
        else:
            target_height = image.height
        
        return image.resize((target_width, target_height), Image.Resampling.LANCZOS)
    
    # ==================== POSITION CALCULATION ====================
    
    def _calculate_signature_position(self, page_width: int, page_height: int) -> Optional[Tuple[int, int]]:
        """Calculate signature position in bottom-right corner."""
        if not self.signature_image:
            return None
        
        # Calculate position from bottom-right with margin
        sig_width = self.signature_image.width
        sig_height = self.signature_image.height
        
        x = self._calculate_position_from_edge(
            page_width, sig_width, self.SIGNATURE_HORIZONTAL_POSITION,
            self.ELEMENTS_MIN_MARGIN, from_bottom_or_right=True
        )
        
        y = self._calculate_position_from_edge(
            page_height, sig_height, self.SIGNATURE_VERTICAL_POSITION,
            self.ELEMENTS_MIN_MARGIN, from_bottom_or_right=True
        )
        
        return x, y
    
    def _calculate_elements_position(
        self, 
        page_width: int, 
        page_height: int,
        combined_width: int,
        combined_height: int,
        signature_y: int
    ) -> Tuple[int, int]:
        """
        Calculate position for combined department list + comments block.
        Places block above signature, right-aligned.
        """
        # Position from right edge, aligned with signature
        x = self._calculate_position_from_edge(
            page_width, combined_width, self.SIGNATURE_HORIZONTAL_POSITION,
            self.ELEMENTS_MIN_MARGIN, from_bottom_or_right=True
        )
        
        # Position above signature with small gap
        gap = 10  # Small gap between block and signature
        y = signature_y - combined_height - gap
        
        # Ensure block doesn't go above top margin
        min_y = int(page_height * self.ELEMENTS_MIN_MARGIN)
        y = max(min_y, y)
        
        return x, y
    
    # ==================== DOCUMENT PROCESSING ====================
    
    def _process_page_image(self, page_img: Image.Image) -> Image.Image:
        """Add signature and elements to a single page image."""
        # Create working copy
        result_img = page_img.copy()
        if result_img.mode != 'RGBA':
            result_img = result_img.convert('RGBA')
        
        page_width, page_height = result_img.size
        
        # Resize signature and comments images proportionally
        if self.signature_image:
            sig_target_width = int(page_width * self.SIGNATURE_SCALE_FACTOR)
            self.signature_image = self._resize_to_width(self.signature_image, sig_target_width)
        
        if self.comments_image:
            comments_target_width = int(page_width * self.COMMENTS_SCALE_FACTOR)
            self.comments_image = self._resize_to_width(self.comments_image, comments_target_width)
        
        # Create department list image
        dept_max_width = int(page_width * self.DEPARTMENT_SCALE_FACTOR)
        department_img = self._render_department_list(dept_max_width)
        
        # Build a single row: comments -> department list -> signature (signature on far right)
        row_img = None
        gap = self.SIDE_BY_SIDE_GAP_PIXELS
        
        if department_img and self.comments_image:
            # comments + department (+ signature if present)
            total_width = self.comments_image.width + gap + department_img.width
            if self.signature_image:
                total_width += gap + self.signature_image.width
            
            # Ensure combined width doesn't exceed limit
            max_combined_width = int(page_width * self.SIDE_BY_SIDE_MAX_WIDTH_RATIO)
            if total_width > max_combined_width:
                # Scale down proportionally
                scale_factor = max_combined_width / total_width
                department_img = self._resize_to_width(department_img, max(1, int(department_img.width * scale_factor)))
                self.comments_image = self._resize_to_width(self.comments_image, max(1, int(self.comments_image.width * scale_factor)))
                if self.signature_image:
                    self.signature_image = self._resize_to_width(self.signature_image, max(1, int(self.signature_image.width * scale_factor)))

                total_width = self.comments_image.width + gap + department_img.width
                if self.signature_image:
                    total_width += gap + self.signature_image.width
            
            # Create combined image
            row_height = max(
                department_img.height,
                self.comments_image.height,
                self.signature_image.height if self.signature_image else 0,
            )
            row_img = Image.new(
                'RGBA', 
                (total_width, row_height),
                (0, 0, 0, 0)
            )
            
            # Paste comments (left)
            comments_y = (row_img.height - self.comments_image.height) // 2
            row_img.paste(self.comments_image, (0, comments_y), self.comments_image)

            # Paste department list (middle)
            dept_y = (row_img.height - department_img.height) // 2
            dept_x = self.comments_image.width + gap
            row_img.paste(
                department_img,
                (dept_x, dept_y),
                department_img,
            )

            # Paste signature (right of department list)
            if self.signature_image:
                sig_y = (row_img.height - self.signature_image.height) // 2
                sig_x = dept_x + department_img.width + gap
                row_img.paste(self.signature_image, (sig_x, sig_y), self.signature_image)
        
        elif department_img and self.signature_image:
            # department -> signature
            total_width = department_img.width + gap + self.signature_image.width

            max_combined_width = int(page_width * self.SIDE_BY_SIDE_MAX_WIDTH_RATIO)
            if total_width > max_combined_width:
                scale_factor = max_combined_width / total_width
                department_img = self._resize_to_width(department_img, max(1, int(department_img.width * scale_factor)))
                self.signature_image = self._resize_to_width(self.signature_image, max(1, int(self.signature_image.width * scale_factor)))
                total_width = department_img.width + gap + self.signature_image.width

            row_height = max(department_img.height, self.signature_image.height)
            row_img = Image.new('RGBA', (total_width, row_height), (0, 0, 0, 0))

            dept_y = (row_img.height - department_img.height) // 2
            row_img.paste(department_img, (0, dept_y), department_img)

            sig_y = (row_img.height - self.signature_image.height) // 2
            row_img.paste(self.signature_image, (department_img.width + gap, sig_y), self.signature_image)

        elif self.comments_image and self.signature_image:
            # comments -> signature
            total_width = self.comments_image.width + gap + self.signature_image.width

            max_combined_width = int(page_width * self.SIDE_BY_SIDE_MAX_WIDTH_RATIO)
            if total_width > max_combined_width:
                scale_factor = max_combined_width / total_width
                self.comments_image = self._resize_to_width(self.comments_image, max(1, int(self.comments_image.width * scale_factor)))
                self.signature_image = self._resize_to_width(self.signature_image, max(1, int(self.signature_image.width * scale_factor)))
                total_width = self.comments_image.width + gap + self.signature_image.width

            row_height = max(self.comments_image.height, self.signature_image.height)
            row_img = Image.new('RGBA', (total_width, row_height), (0, 0, 0, 0))

            comments_y = (row_img.height - self.comments_image.height) // 2
            row_img.paste(self.comments_image, (0, comments_y), self.comments_image)

            sig_y = (row_img.height - self.signature_image.height) // 2
            row_img.paste(self.signature_image, (self.comments_image.width + gap, sig_y), self.signature_image)

        elif department_img:
            row_img = department_img
        elif self.comments_image:
            row_img = self.comments_image
        elif self.signature_image:
            row_img = self.signature_image
        
        # Stamp the final row bottom-right (with margins)
        if row_img:
            block_x = self._calculate_position_from_edge(
                page_width,
                row_img.width,
                self.SIGNATURE_HORIZONTAL_POSITION,
                self.ELEMENTS_MIN_MARGIN,
                from_bottom_or_right=True,
            )
            block_y = self._calculate_position_from_edge(
                page_height,
                row_img.height,
                self.SIGNATURE_VERTICAL_POSITION,
                self.ELEMENTS_MIN_MARGIN,
                from_bottom_or_right=True,
            )
            result_img.paste(row_img, (block_x, block_y), row_img)
        
        return result_img
    
    def _process_pdf(self, pdf_bytes: bytes) -> bytes:
        """Process PDF document."""
        try:
            # Read original PDF
            reader = PdfReader(BytesIO(pdf_bytes))
            writer = PdfWriter()
            
            # Process each page
            for page_num, page in enumerate(reader.pages):
                # Convert page to image
                page_images = convert_from_bytes(pdf_bytes, first_page=page_num+1, last_page=page_num+1, dpi=150)
                if not page_images:
                    writer.add_page(page)
                    continue
                
                page_img = page_images[0]
                
                # Process the page image
                processed_img = self._process_page_image(page_img)
                
                # Convert back to PDF page
                from reportlab.pdfgen import canvas
                from reportlab.lib.utils import ImageReader
                
                temp_pdf = BytesIO()
                c = canvas.Canvas(temp_pdf, pagesize=page_img.size)
                
                # Draw processed image
                img_reader = ImageReader(processed_img)
                c.drawImage(img_reader, 0, 0, width=page_img.width, height=page_img.height)
                c.save()
                
                # Add processed page
                temp_pdf.seek(0)
                processed_reader = PdfReader(temp_pdf)
                writer.add_page(processed_reader.pages[0])
            
            # Save to bytes
            output = BytesIO()
            writer.write(output)
            return output.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to process PDF: {str(e)}")
    
    def _process_image(self, image_bytes: bytes) -> bytes:
        """Process image document."""
        try:
            # Open and process image
            img = Image.open(BytesIO(image_bytes))
            
            # Preserve original format and EXIF
            original_format = img.format
            original_mode = img.mode
            
            if hasattr(img, '_getexif'):
                exif = img._getexif()
            else:
                exif = None
            
            # Process image
            processed_img = self._process_page_image(img)
            
            # Convert back to original format if needed
            if original_mode != 'RGBA' and processed_img.mode == 'RGBA':
                if original_mode == 'RGB':
                    processed_img = processed_img.convert('RGB')
                elif original_mode == 'L':
                    processed_img = processed_img.convert('L')
                elif original_mode == 'P':
                    processed_img = processed_img.convert('P')
            
            # Save to bytes
            output = BytesIO()
            
            save_args = {'format': original_format or 'PNG'}
            if exif and original_format in ['JPEG', 'TIFF']:
                save_args['exif'] = exif
            
            processed_img.save(output, **save_args)
            return output.getvalue()
            
        except Exception as e:
            raise Exception(f"Failed to process image: {str(e)}")
    
    # ==================== PUBLIC INTERFACE ====================
    
    def process_document(self) -> bool:
        """
        Process the document by adding signature, comments, and department list.
        
        Returns:
            True if successful, raises exception otherwise
        """
        if not self.signature_model.attachment.file:
            raise ValueError("No document attachment found")
        
        # Decode signature and comments
        self._decode_signature()
        self._decode_comments()
        
        # Get the attachment
        attachment = self.signature_model.attachment
        file_name = attachment.file.name.lower()
        
        try:
            # Read file content
            with attachment.file.open('rb') as f:
                file_content = f.read()
            
            # Process based on file type
            if file_name.endswith('.pdf'):
                processed_content = self._process_pdf(file_content)
            elif any(file_name.endswith(ext) for ext in self.IMAGE_EXTENSIONS):
                processed_content = self._process_image(file_content)
            else:
                raise ValueError(f"Unsupported file format: {Path(file_name).suffix}")
            
            # Save processed file
            timestamp = int(datetime.now().timestamp())
            file_ext = Path(file_name).suffix
            new_filename = f"signed_{timestamp}{file_ext}"
            
            file_like_obj = ContentFile(processed_content, name=new_filename)
            attachment.file = file_like_obj
            attachment.is_signed = True
            attachment.save()
            
            # Update document status
            self.document.status = 'signed'
            self.document.save()
            
            return True
            
        except Exception as e:
            raise Exception(f"Failed to process document: {str(e)}")
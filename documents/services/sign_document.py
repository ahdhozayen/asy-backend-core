import base64
from datetime import datetime
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PyPDF2 import PdfReader, PdfWriter
import arabic_reshaper
from bidi.algorithm import get_display
from django.core.files.base import ContentFile
from pdf2image import convert_from_bytes

class SignatureAgent:
    """
    A class to handle document signing with base64-encoded signatures and comments.
    Supports both PDF and image documents.
    
    Positioning System:
    -------------------
    The class uses percentage-based positioning to ensure consistent placement of
    signatures and comments across different document sizes (A4, Letter, Legal, etc.).
    
    Percentage-based positioning:
    - Positions are calculated as percentages (0.0 to 1.0) of document dimensions
    - SIGNATURE_HORIZONTAL_POSITION: 0.85 = 85% from left (right-aligned)
    - SIGNATURE_VERTICAL_POSITION = 0.95    # 95% from top (bottom-aligned)
    - PADDING_PERCENTAGE = 0.02             # 2% padding as minimum margin from edges
    
    Layout:
    - Signature: Bottom-right corner with configurable padding
    - Comments: Positioned directly above signature with minimal gap
    
    Example:
    --------
    To position signature at 90% from left and 97% from top:
        SignatureAgent.SIGNATURE_HORIZONTAL_POSITION = 0.90
        SignatureAgent.SIGNATURE_VERTICAL_POSITION = 0.97
    """
    
    # Supported image extensions
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg'}
    
    # Percentage-based position configuration (0.0 to 1.0)
    # These values represent position as a percentage of document dimensions
    SIGNATURE_HORIZONTAL_POSITION = 0.50  # 85% from left (right-aligned)
    SIGNATURE_VERTICAL_POSITION = 0.90    # 95% from top (bottom-aligned)
    PADDING_PERCENTAGE = 0             # 2% padding as minimum margin from edges
    
    # Comments positioning relative to signature (in pixels, not percentage)
    # Reduced to minimal gap between comments and signature
    COMMENTS_VERTICAL_GAP_PIXELS = 0      # Only 5 pixels gap between comments and signature
    COMMENTS_HORIZONTAL_ALIGN = True      # True = center align with signature, False = same x position

    # Department list positioning (percentage-based)
    # Department list is centered horizontally; vertical position is used as fallback when signature isn't present.
    DEPARTMENT_LIST_HORIZONTAL_POSITION = 0.50  # 50% = center of page (center-aligned)
    DEPARTMENT_LIST_VERTICAL_POSITION = 0.90    # 90% from top (near bottom, bottom-aligned)
    DEPARTMENT_LIST_SIDE_GAP_PIXELS = 0     # Gap between department list and comments image
    
    
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
    
    @staticmethod
    def _validate_percentage(value, name='percentage'):
        """
        Validate that a percentage value is within valid range (0.0 to 1.0).
        
        Args:
            value: The percentage value to validate
            name: Name of the parameter for error messages
            
        Returns:
            float: Validated percentage value
            
        Raises:
            ValueError: If value is outside valid range
        """
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be a number")
        if value < 0.0 or value > 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")
        return float(value)
    
    @staticmethod
    def _calculate_percentage_position(
        document_dimension, 
        element_dimension, 
        percentage, 
        padding_percentage=None,
        align_right=False,
        align_bottom=False
    ):
        """
        Calculate absolute position based on percentage of document dimension.
        
        Args:
            document_dimension: Width or height of the document (pixels)
            element_dimension: Width or height of the element to position (pixels)
            percentage: Position as percentage (0.0 to 1.0)
            padding_percentage: Optional padding to apply (0.0 to 1.0)
            align_right: If True, position is calculated from right edge
            align_bottom: If True, position is calculated from bottom edge
            
        Returns:
            int: Absolute position in pixels
        """
        # Validate percentage
        percentage = SignatureAgent._validate_percentage(percentage, 'percentage')
        
        # Calculate base position from percentage
        if align_right or align_bottom:
            # For right/bottom alignment: position is calculated from the edge
            # percentage represents where the right/bottom edge should be
            position = document_dimension * percentage - element_dimension
        else:
            # For left/top alignment: position is calculated from the start
            # percentage represents where the left/top edge should be
            position = document_dimension * percentage
        
        # Apply padding constraints if provided
        if padding_percentage is not None:
            padding = SignatureAgent._validate_percentage(padding_percentage, 'padding_percentage')
            padding_pixels = document_dimension * padding
            
            if align_right or align_bottom:
                # For right/bottom alignment:
                # - Ensure element doesn't exceed padding from right/bottom edge
                max_position = document_dimension - element_dimension - padding_pixels
                # - Ensure element doesn't exceed padding from left/top edge
                min_position = padding_pixels
                position = max(min_position, min(position, max_position))
            else:
                # For left/top alignment:
                # - Ensure element doesn't exceed padding from left/top edge
                min_position = padding_pixels
                # - Ensure element doesn't exceed padding from right/bottom edge
                max_position = document_dimension - element_dimension - padding_pixels
                position = max(min_position, min(position, max_position))
        else:
            # No padding, just ensure position is within document bounds
            if align_right or align_bottom:
                position = max(0, position)
            else:
                position = max(0, min(position, document_dimension - element_dimension))
        
        return int(position)

    @staticmethod
    def _calculate_percentage_center_position(
        document_dimension,
        element_dimension,
        percentage,
        padding_percentage=None,
    ):
        """
        Calculate absolute position where the *center* of the element is placed at the given percentage.
        """
        percentage = SignatureAgent._validate_percentage(percentage, 'percentage')
        position = (document_dimension * percentage) - (element_dimension / 2)

        if padding_percentage is not None:
            padding = SignatureAgent._validate_percentage(padding_percentage, 'padding_percentage')
            padding_pixels = document_dimension * padding
            min_position = padding_pixels
            max_position = document_dimension - element_dimension - padding_pixels
            position = max(min_position, min(position, max_position))
        else:
            position = max(0, min(position, document_dimension - element_dimension))

        return int(position)
    
    def _calculate_signature_position(self, doc_width, doc_height, signature_width, signature_height):
        """
        Calculate signature position using percentage-based positioning.
        
        Args:
            doc_width: Document width in pixels
            doc_height: Document height in pixels
            signature_width: Signature image width in pixels
            signature_height: Signature image height in pixels
            
        Returns:
            tuple: (x, y) position in pixels
        """
        # Percentage-based positioning (bottom-right corner)
        x = self._calculate_percentage_position(
            doc_width,
            signature_width,
            SignatureAgent.SIGNATURE_HORIZONTAL_POSITION,
            padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
            align_right=True
        )
        
        y = self._calculate_percentage_position(
            doc_height,
            signature_height,
            SignatureAgent.SIGNATURE_VERTICAL_POSITION,
            padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
            align_bottom=True
        )
        
        return (x, y)
    
    def _calculate_comments_position(
        self, 
        doc_width, 
        doc_height, 
        comments_width, 
        comments_height,
        signature_x=None,
        signature_y=None,
        signature_height=None,
        signature_width=None
    ):
        """
        Calculate comments position to be directly above signature with minimal gap.
        
        Args:
            doc_width: Document width in pixels
            doc_height: Document height in pixels
            comments_width: Comments image width in pixels
            comments_height: Comments image height in pixels
            signature_x: Signature X position (for alignment)
            signature_y: Signature Y position (for positioning above)
            signature_height: Signature height
            signature_width: Signature width (for horizontal alignment)
            
        Returns:
            tuple: (x, y) position in pixels
        """
        # If we have signature position, position comments directly above it
        if signature_x is not None and signature_y is not None:
            # Horizontal positioning: center-align comments with signature
            if SignatureAgent.COMMENTS_HORIZONTAL_ALIGN and signature_width is not None:
                # Center comments above signature
                x = signature_x + (signature_width - comments_width)
            else:
                # Use same x position as signature (left-aligned)
                x = signature_x
                
            # Ensure not off-page horizontally
            x = max(int(doc_width * SignatureAgent.PADDING_PERCENTAGE), 
                   min(x, doc_width - comments_width - int(doc_width * SignatureAgent.PADDING_PERCENTAGE)))
            
            # Vertical positioning: DIRECTLY above signature with minimal gap
            # Position comments so its bottom edge is just above signature's top edge
            y = signature_y - comments_height - SignatureAgent.COMMENTS_VERTICAL_GAP_PIXELS
            
            # Ensure not off the top of the page
            min_y = int(doc_height * SignatureAgent.PADDING_PERCENTAGE)
            y = max(min_y, y)
            
        else:
            # Fallback: position using percentage (for when signature is not present)
            x = self._calculate_percentage_position(
                doc_width,
                comments_width,
                SignatureAgent.SIGNATURE_HORIZONTAL_POSITION,
                padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
                align_right=True
            )
            
            # Position higher than signature would be (since signature is at 95%, put comments at 90%)
            y = self._calculate_percentage_position(
                doc_height,
                comments_height,
                SignatureAgent.SIGNATURE_VERTICAL_POSITION - 0.05,  # 5% above signature position
                padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
                align_bottom=True
            )
        
        return (x, y)

    def _calculate_department_list_position(
        self,
        doc_width,
        doc_height,
        element_width,
        element_height,
        signature_y=None,
        block_height=None,
    ):
        """
        Calculate department list position.

        - Horizontal: centered using DEPARTMENT_LIST_HORIZONTAL_POSITION
        - Vertical: aligned relative to signature when available; otherwise percentage-based fallback
        """
        x = self._calculate_percentage_center_position(
            doc_width,
            element_width,
            SignatureAgent.DEPARTMENT_LIST_HORIZONTAL_POSITION,
            padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
        )

        if signature_y is not None and block_height is not None:
            y_block = signature_y - block_height - SignatureAgent.COMMENTS_VERTICAL_GAP_PIXELS
            min_y = int(doc_height * SignatureAgent.PADDING_PERCENTAGE)
            y_block = max(min_y, y_block)
            y = y_block + max(0, int((block_height - element_height) / 2))
        else:
            y = self._calculate_percentage_position(
                doc_height,
                element_height,
                SignatureAgent.DEPARTMENT_LIST_VERTICAL_POSITION,
                padding_percentage=SignatureAgent.PADDING_PERCENTAGE,
                align_bottom=True,
            )

        return (x, int(y))

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

            # Handle empty data URLs like: "data:image/png;base64,"
            if not base64_str or not base64_str.strip():
                self.comments_image = None
                return True

            # Decode base64 to bytes and create PIL Image
            comments_data = base64.b64decode(base64_str)
            self.comments_image = Image.open(BytesIO(comments_data)).convert('RGBA')
            return True
        except Exception as e:
            raise ValueError(f"Failed to decode comments: {str(e)}")

    @staticmethod
    def _get_default_font(font_size):
        """
        Try to load a font that supports Arabic. Falls back to PIL default font.
        """
        candidates = [
            # Windows (common on deployments / dev)
            r"C:\Windows\Fonts\arial.ttf",
            r"C:\Windows\Fonts\Arial.ttf",
            r"C:\Windows\Fonts\tahoma.ttf",
            r"C:\Windows\Fonts\Tahoma.ttf",
            # Linux common
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        ]
        for path in candidates:
            try:
                return ImageFont.truetype(path, font_size)
            except Exception:
                continue
        return ImageFont.load_default()

    def _normalize_department_list(self):
        value = getattr(self.signature_model, 'department_list', None)
        if not value:
            return []
        if isinstance(value, list):
            return [str(x) for x in value if str(x).strip()]
        return []

    def _render_department_list_image(
        self,
        departments,
        max_width_px,
        font_size=26,
        padding_px=10,
        line_spacing_px=6,
        color_rgba=(255, 0, 0, 255),
    ):
        """
        Render department_list as a transparent RGBA image with bullet points.
        """
        if not departments:
            return None

        font = self._get_default_font(font_size)
        dummy = Image.new('RGBA', (10, 10), (0, 0, 0, 0))
        draw = ImageDraw.Draw(dummy)

        def measure(text):
            left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
            return right - left, bottom - top

        def shape(text):
            # IMPORTANT: reshape+bidi AFTER wrapping. Never split shaped/bidi text.
            return self._format_arabic_text(text)

        def is_arabic(text):
            return any('\u0600' <= ch <= '\u06FF' for ch in text)

        bullet = '•'
        bullet_w, bullet_h = measure(bullet)
        bullet_gap_px = 8
        bullet_area_px = bullet_w + bullet_gap_px

        def wrap_logical_text(logical_text, max_line_width):
            """
            Width-based wrapping on logical text, measuring shaped output each step.
            Returns list of logical lines (not shaped yet).
            """
            words = logical_text.split()
            if not words:
                return []

            lines = []
            current = ''
            for word in words:
                candidate = word if not current else f'{current} {word}'
                w, _ = measure(shape(candidate))
                if w <= max_line_width:
                    current = candidate
                    continue

                if current:
                    lines.append(current)
                    current = word
                else:
                    # Single very long word: accept it as-is (it will overflow max_width_px)
                    lines.append(candidate)
                    current = ''

            if current:
                lines.append(current)

            return lines

        rendered_lines = []  # [{text, is_ar, is_first}]
        for dept in departments:
            dept = dept.strip()
            if not dept:
                continue

            # Bullet list: keep it visually like HTML <ul><li>
            # For Arabic RTL, we wrap on logical text then shape per final line.
            ar = is_arabic(dept)
            if ar:
                max_line_width = max_width_px - (padding_px * 2) - bullet_area_px
            else:
                max_line_width = max_width_px - (padding_px * 2)

            logical_lines = wrap_logical_text(dept, max_line_width=max_line_width)
            for idx, logical_line in enumerate(logical_lines):
                rendered_lines.append({
                    'text': shape(logical_line) if ar else f'{bullet} {logical_line}' if idx == 0 else f'  {logical_line}',
                    'is_ar': ar,
                    'is_first': idx == 0,
                })

        if not rendered_lines:
            return None

        # Compute final image size
        widths = []
        heights = []
        for line in rendered_lines:
            w, h = measure(line['text'])
            widths.append(w)
            heights.append(h)

        max_text_width = max(widths) if widths else 0
        # For Arabic, reserve bullet area on the right
        any_ar = any(x['is_ar'] for x in rendered_lines)
        reserved_px = bullet_area_px if any_ar else 0
        text_width = min(max_text_width, max_width_px - (padding_px * 2) - reserved_px)
        total_height = sum(heights) + (line_spacing_px * (len(rendered_lines) - 1))

        img_w = min(max_width_px, text_width + reserved_px + (padding_px * 2))
        img_h = total_height + (padding_px * 2)

        out = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 0))
        out_draw = ImageDraw.Draw(out)

        y = padding_px
        for line in rendered_lines:
            text = line['text']
            w, h = measure(text)

            if line['is_ar']:
                # RTL list: bullet on the RIGHT, text right-aligned before it
                bullet_x = img_w - padding_px - bullet_w
                out_draw.text((bullet_x, y), bullet, font=font, fill=color_rgba)

                text_right_pad = padding_px + bullet_area_px
                text_x = max(padding_px, img_w - text_right_pad - w)
                out_draw.text((text_x, y), text, font=font, fill=color_rgba)
            else:
                # LTR list: bullet on the left (already prefixed in text)
                out_draw.text((padding_px, y), text, font=font, fill=color_rgba)

            y += h + line_spacing_px

        return out

    @staticmethod
    def _combine_side_by_side(left_img, right_img, gap_px=16):
        if left_img is None and right_img is None:
            return None
        if left_img is None:
            return right_img
        if right_img is None:
            return left_img

        left = left_img.convert('RGBA') if left_img.mode != 'RGBA' else left_img
        right = right_img.convert('RGBA') if right_img.mode != 'RGBA' else right_img

        width = left.width + gap_px + right.width
        height = max(left.height, right.height)
        out = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        out.paste(left, (0, 0), left)
        out.paste(right, (left.width + gap_px, 0), right)
        return out

    @staticmethod
    def _resize_to_max_width(image, max_width_px):
        if image is None:
            return None
        if max_width_px <= 0:
            return None
        if image.width <= max_width_px:
            return image

        scale = max_width_px / image.width
        new_height = max(1, int(image.height * scale))
        return image.resize((max_width_px, new_height), Image.Resampling.LANCZOS)
    
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
            # Scale factors are percentage-based relative to document width
            resized_signature = self._resize_image(self.signature_image, first_page_img.width, scale_factor=0.25)
            resized_comments = self._resize_image(self.comments_image, first_page_img.width, scale_factor=0.5)

            # Render department_list as bullet points (Arabic-safe shaping)
            departments = self._normalize_department_list()
            departments_img = self._render_department_list_image(
                departments=departments,
                max_width_px=int(first_page_img.width * 0.30),
            )

            # Calculate signature position
            signature_x = None
            signature_y = None
            signature_width = None
            signature_height = None
            
            if resized_signature:
                signature_width = resized_signature.width
                signature_height = resized_signature.height
                signature_x, signature_y = self._calculate_signature_position(
                    first_page_img.width,
                    first_page_img.height,
                    signature_width,
                    signature_height
                )

                # Ensure signature has transparency
                if resized_signature.mode != 'RGBA':
                    resized_signature = resized_signature.convert('RGBA')

                # Paste signature with transparency
                first_page_img.paste(
                    resized_signature,
                    (signature_x, signature_y),
                    resized_signature
                )

            # Process department list + comments (side-by-side) if available
            padding_px = int(first_page_img.width * SignatureAgent.PADDING_PERCENTAGE)
            if departments_img or resized_comments:
                dept = departments_img.convert('RGBA') if departments_img and departments_img.mode != 'RGBA' else departments_img
                comm = resized_comments.convert('RGBA') if resized_comments and resized_comments.mode != 'RGBA' else resized_comments

                block_height = max(dept.height if dept else 0, comm.height if comm else 0)

                if dept:
                    dept_x, dept_y = self._calculate_department_list_position(
                        first_page_img.width,
                        first_page_img.height,
                        dept.width,
                        dept.height,
                        signature_y=signature_y,
                        block_height=block_height,
                    )

                    # Paste department list first (centered)
                    first_page_img.paste(dept, (dept_x, dept_y), dept)

                    if comm:
                        # Decide whether comments go to right or left of department list
                        gap = SignatureAgent.DEPARTMENT_LIST_SIDE_GAP_PIXELS
                        available_right = (first_page_img.width - padding_px) - (dept_x + dept.width + gap)
                        available_left = (dept_x - gap) - padding_px

                        place_right = available_right >= available_left
                        available = available_right if place_right else available_left

                        comm = self._resize_to_max_width(comm, int(available))
                        if comm:
                            if place_right:
                                comm_x = dept_x + dept.width + gap
                            else:
                                comm_x = dept_x - gap - comm.width

                            comm_y = int((signature_y - block_height - SignatureAgent.COMMENTS_VERTICAL_GAP_PIXELS) if signature_y is not None else dept_y)
                            comm_y = comm_y + max(0, int((block_height - comm.height) / 2))
                            comm_x = max(padding_px, min(comm_x, first_page_img.width - comm.width - padding_px))
                            comm_y = max(int(first_page_img.height * SignatureAgent.PADDING_PERCENTAGE),
                                         min(comm_y, first_page_img.height - comm.height - int(first_page_img.height * SignatureAgent.PADDING_PERCENTAGE)))
                            first_page_img.paste(comm, (comm_x, comm_y), comm)

                else:
                    # No department list; fall back to original comments positioning above signature
                    if comm:
                        comments_x, comments_y = self._calculate_comments_position(
                            first_page_img.width,
                            first_page_img.height,
                            comm.width,
                            comm.height,
                            signature_x=signature_x,
                            signature_y=signature_y,
                            signature_height=signature_height,
                            signature_width=signature_width,
                        )
                        first_page_img.paste(comm, (comments_x, comments_y), comm)
            
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

            # Resize signature and comments images
            resized_signature = self._resize_image(self.signature_image, img.width, scale_factor=0.25)
            resized_comments = self._resize_image(self.comments_image, img.width, scale_factor=0.5)

            # Render department_list as bullet points (Arabic-safe shaping)
            departments = self._normalize_department_list()
            departments_img = self._render_department_list_image(
                departments=departments,
                max_width_px=int(img.width * 0.30),
            )

            # Calculate signature position
            signature_x = None
            signature_y = None
            signature_width = None
            signature_height = None

            if resized_signature:
                signature_width = resized_signature.width
                signature_height = resized_signature.height
                signature_x, signature_y = self._calculate_signature_position(
                    img.width,
                    img.height,
                    signature_width,
                    signature_height
                )

                # Ensure signature has transparency
                if resized_signature.mode != 'RGBA':
                    resized_signature = resized_signature.convert('RGBA')

                # Paste signature with transparency
                img.paste(
                    resized_signature,
                    (signature_x, signature_y),
                    resized_signature
                )

            # Process department list + comments (side-by-side) if available
            padding_px = int(img.width * SignatureAgent.PADDING_PERCENTAGE)
            if departments_img or resized_comments:
                dept = departments_img.convert('RGBA') if departments_img and departments_img.mode != 'RGBA' else departments_img
                comm = resized_comments.convert('RGBA') if resized_comments and resized_comments.mode != 'RGBA' else resized_comments

                block_height = max(dept.height if dept else 0, comm.height if comm else 0)

                if dept:
                    dept_x, dept_y = self._calculate_department_list_position(
                        img.width,
                        img.height,
                        dept.width,
                        dept.height,
                        signature_y=signature_y,
                        block_height=block_height,
                    )

                    img.paste(dept, (dept_x, dept_y), dept)

                    if comm:
                        gap = SignatureAgent.DEPARTMENT_LIST_SIDE_GAP_PIXELS
                        available_right = (img.width - padding_px) - (dept_x + dept.width + gap)
                        available_left = (dept_x - gap) - padding_px

                        place_right = available_right >= available_left
                        available = available_right if place_right else available_left

                        comm = self._resize_to_max_width(comm, int(available))
                        if comm:
                            if place_right:
                                comm_x = dept_x + dept.width + gap
                            else:
                                comm_x = dept_x - gap - comm.width

                            comm_y = int((signature_y - block_height - SignatureAgent.COMMENTS_VERTICAL_GAP_PIXELS) if signature_y is not None else dept_y)
                            comm_y = comm_y + max(0, int((block_height - comm.height) / 2))
                            comm_x = max(padding_px, min(comm_x, img.width - comm.width - padding_px))
                            comm_y = max(int(img.height * SignatureAgent.PADDING_PERCENTAGE),
                                         min(comm_y, img.height - comm.height - int(img.height * SignatureAgent.PADDING_PERCENTAGE)))
                            img.paste(comm, (comm_x, comm_y), comm)

                else:
                    if comm:
                        comments_x, comments_y = self._calculate_comments_position(
                            img.width,
                            img.height,
                            comm.width,
                            comm.height,
                            signature_x=signature_x,
                            signature_y=signature_y,
                            signature_height=signature_height,
                            signature_width=signature_width,
                        )
                        img.paste(comm, (comments_x, comments_y), comm)
            
            # Convert back to original format
            output = BytesIO()

            if original_mode != 'RGBA' and img.mode == 'RGBA':
                if original_mode == 'RGB':
                    img = img.convert('RGB')
                elif original_mode == 'L':
                    img = img.convert('L')
                elif original_mode == 'P':
                    img = img.convert('P')

            # Determine format
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
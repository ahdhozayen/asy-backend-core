from drf_yasg.inspectors import TagsOpenAPIViewInspector
from drf_yasg.utils import get_serializer_class


class AppNameTagsInspector(TagsOpenAPIViewInspector):
    """
    Custom tag inspector that uses the app name as the tag instead of 'api'.
    """
    def get_tags(self, operation_keys=None):
        """
        Get the tags for the operation based on the app name.
        
        Args:
            operation_keys: List of keys that describe the operation
            
        Returns:
            List of tags for the operation
        """
        if operation_keys and len(operation_keys) > 1:
            # Use the app name as the tag
            app_name = operation_keys[0]
            # Capitalize the app name for better display
            return [app_name.capitalize()]
        
        # Fallback to default behavior
        return super().get_tags(operation_keys)

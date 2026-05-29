import base64
import io
from ..constants.image_constants import IMAGE_SIZES
from PIL import Image


class ImageUtility:
    @staticmethod
    def resize_images(image_data):
        # Decode the base64 image data
        original_image = ImageUtility._decode_image(image_data)
        # Determine the format of the image from the original file
        image_format = original_image.format if original_image.format else "PNG"

        resized_images = {}

        # Iterate over predefined sizes and resize images
        for size_name, size in IMAGE_SIZES.items():
            try:
                # Resize the image
                resized_image = ImageUtility._resize_image(original_image, size)

                # Encode resized image to base64
                resized_image_data = ImageUtility._encode_image(resized_image, image_format)

                # Add resized image data to the dictionary
                resized_images[size_name] = resized_image_data

            except Exception as e:
                # Log or handle any error during the resizing process (optional)
                print(f"Error processing size {size_name}: {e}")

        return resized_images

    @staticmethod
    def _resize_image(image, size):
        """
        Resizes a PIL image to the specified size.
        :param image: The original PIL image object.
        :param size: A tuple (width, height) representing the target size.
        :return: The resized PIL image.
        """
        resized_image = image.copy()
        resized_image.thumbnail(size, Image.ANTIALIAS)
        return resized_image

    @staticmethod
    def _decode_image(image_data):
        """
        Decodes a base64 image string into a PIL Image object.
        :param image_data: Base64 encoded image data.
        :return: A PIL image object.
        """
        image_binary = image_data
        if not isinstance(image_binary, bytes):
            image_binary = base64.b64decode(image_data)
        image_stream = io.BytesIO(image_binary)
        return Image.open(image_stream)

    @staticmethod
    def _encode_image(image, image_format):
        """
        Encodes a PIL image object into a base64 string.
        :param image: A PIL image object.
        :param image_format: The format to save the image in (e.g., 'PNG', 'JPEG').
        :return: Base64 encoded string of the image.
        """
        image_buffer = io.BytesIO()
        image.save(image_buffer, format=image_format)
        image_binary = image_buffer.getvalue()
        return base64.b64encode(image_binary).decode('utf-8')
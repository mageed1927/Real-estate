import os


class FileUtility:
    @staticmethod
    def extract_extension(file_name):
        # Use os.path.splitext to split the file name into base name and extension
        base_name, extension = os.path.splitext(file_name)

        # Check if the extension is empty
        if not extension:
            # If the extension is empty, assume it's a file without an extension
            return ""

        return base_name, extension

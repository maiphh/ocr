# from document_loader_api import read_file
# from mistral_ocr import read_file_mistral
# from pathlib import Path
# import time

# path = "/Users/phu.mai/Projects/ocr/data"

# def get_all_files(root) -> list[str]:
#     """Get all files from a directory recursively"""
#     p = Path(root)
#     if not p.exists() or not p.is_dir():
#         raise ValueError(f"Provided root path '{root}' is not a valid directory.")
#     return [str(f) for f in p.rglob("*") if f.is_file()]

# def test_read_file_time():
#     files = get_all_files(path)
#     files_num = len(files)
#     total_time = 0.0
#     for file in files:
#         start = time.time()
#         result = read_file_mistral(file)
#         end = time.time()
#         duration = end - start
#         total_time += duration
#         print(f"Time taken to process {file}: {duration} seconds")
#     avg_time = total_time / files_num if files_num > 0 else 0
#     print(f"Processed {files_num} files. Average time per file: {avg_time} seconds")

# def test_read_file_mistral_time():
#     files = get_all_files(path)
#     files_num = len(files)
#     total_time = 0.0
#     for file in files:
#         start = time.time()
#         result = read_file_mistral(file)
#         end = time.time()
#         duration = end - start
#         total_time += duration
#         print(f"Time taken to process {file}: {duration} seconds")
#     avg_time = total_time / files_num if files_num > 0 else 0
#     print(f"Processed {files_num} files. Average time per file: {avg_time} seconds")

# if __name__ == "__main__":
#     test_read_file_mistral_time()
#     test_read_file_time()
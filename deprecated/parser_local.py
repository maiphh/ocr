from langchain_ollama import ChatOllama
from langchain_core.documents import Document
import json
class Response:
    def __init__(self, content: str):
        self.name : str= content[0]
        self.dob : str = content[1]
        self.medical_id : str = content[2]
        self.request_type : int = content[3]
        self.sysyem_type : int = content[4]
        self.benefit_group : int = content[5]
        self.personal_id: str = content[6]
        self.start_date : str = content[7]
        self.end_date : str = content[8]
        self.total_days : int = content[9]
        self.disease_code : str = content[10]
        self.disease_name : str = content[11]
        self.document_serial : str = content[12]
        self.ocr_score : str = content[13]

    @staticmethod
    def get_instruction() -> str:
        return """
        Name : str : Name of the patient
        DOB : str : Date of birth of the patient in DD/MM/YYYY format
        Medical ID : str : BHXH or BHYT id (if you see the phrase BHXY or BHYT take the number behind it)
        Request Type : int : put a N/A placeholder
        System Type : int : put a N/A placeholder
        Benefit Group : int : put a N/A placeholder
        Personal ID : str : CCCD/CMND id (if you see the phrase CCC
        Personal ID : str : CCCD/CMND id (if you see the phrase CCCD or CMND take the number behind it)
        Start Date : DD/MM/YYYY : Start date of the treatment
        End Date : DD/MM/YYYY : End date of the treatment
        Total Days : int : Total number of days of treatment by taking end date - start date
        Disease Code : str : The disease code, if any. This usually appear in diagnosises. It may have multiple disease codes, separate them by semicolon ;
        Disease Name : str : The disease name, if any. This usually appear in diagnosises. It may have multiple disease names, separate them by semicolon ;
        Document Serial : str : The serial number of the document, usually stay up top
        OCR Score : str : The OCR score of the document
        """
    def to_list(self) -> list:
        return [self.name,self.dob,self.medical_id,self.request_type,self.sysyem_type,self.benefit_group,self.personal_id,self.start_date,self.end_date,self.total_days,self.disease_code,self.disease_name,self.document_serial,self.ocr_score]
    
    def to_string(self) -> str:
        return f"[{self.name},{self.dob},{self.medical_id},{self.request_type},{self.sysyem_type},{self.benefit_group},{self.personal_id},{self.start_date},{self.end_date},{self.total_days},{self.disease_code},{self.disease_name},{self.document_serial},{self.ocr_score}]"

    
class Parser:
    def __init__(self):
        self.llm = ChatOllama(model="qwen3:8b")
    
    def parse(self,doc: Document) -> dict:
        print("parsing: " + doc.metadata.get("source","unknown"))
        prompt = f"""
            You are an intelligent data extraction system. Your task is to read the following raw text obtained from OCR scanning of a Vietnamese social-insurance document and extract key fields into a **plain comma-separated list** (CSV-style), one record per line.

            **Rules:**
            - Extract information only from the provided text.
            - If a field is not present or cannot be confidently inferred, fill it with "N/A".
            - Do NOT make up data or infer beyond what is explicitly stated.
            - Output must be a plain text list — **not JSON**, **not Markdown**, **no explanation**.
            - Each line represents one record.
            - Fields must appear in this exact order, separated by commas:

            Fields:
            {Response.get_instruction()}

            **Example Output (format only):**
            [Nguyễn Văn A,123456789,Phát sinh mới,1,1,1,012345678,01/01/2023,31/01/2023,30,...]
            [Trần Thị B,987654321,Điều chỉnh,2,3,2,098765432,05/02/2023,15/02/2023,10,...]

            Return ONLY the plain list. No explanations, no extra text.

            Document:
            {doc.page_content}
            """

        response = Response(remove_think_tag(self.llm.invoke([{"role": "user", "content": prompt}]).content).split(","))

        print(response.to_string())
        return response
    
   
def remove_think_tag(text: str) -> str:
    import re
    # Remove <think>...</think> tags and their content
    cleaned_text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return cleaned_text.strip("\n").strip()


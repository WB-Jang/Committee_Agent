import nltk
from langchain_community.document_loaders import UnstructuredWordDocumentLoader

nltk.download('punkt')

def read_docx(file):
  loader = UnstructuredWordDocumentLoader(
      file,
      mode='elements', # 요소 단위 분할
      strategy='hi_res' # 표 구조 인식 활성화
  )
  raw_docs = loader.load()
  grouped_sections = []
  current_section_title = "Introduction"
  current_text_buffer = []

  for doc in raw_docs:
    category = doc.metadata.get("category")
    content = doc.page_content.strip()

    emphasized_contents = doc.metadata.get("emphasized_text_contents",[])
    emphasized_tags = doc.metadata.get("emphasized_text_tags", [])
    is_real_title = False

    if 'b' in emphasized_tags:
      clean_emphasized=' '.join([t.strip() for t in emphasized_contents])
      if content == clean_emphasized:
        is_real_title = True

    if category == "Table":
      html_content = doc.metadata.get("text_as_html","")
      if not html_content:
        html_content = f"<div>{content}</div>"
      formatted_table = f"\n[Table Start]\n{html_content}\n[Table End]\n"
      current_text_buffer.append(formatted_table)
    elif is_real_title:
      # If there's content in the buffer, it belongs to the previous section
      if current_text_buffer:
        grouped_sections.append({
            "title": current_section_title,
            "content": "\n".join(current_text_buffer)
        })
      # Start a new section with the new title
      current_section_title = content # Update the section title
      current_text_buffer = [] # Reset the buffer for the new section
    else:
      current_text_buffer.append(content)

  # After the loop, append any remaining content as the last section
  if current_text_buffer:
    grouped_sections.append({
            "title": current_section_title,
            "content": "\n".join(current_text_buffer)
        })
  return grouped_sections

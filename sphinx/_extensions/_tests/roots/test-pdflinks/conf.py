import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # _extensions/

extensions = ["pdf_links"]
master_doc = "index"
exclude_patterns = ["_build"]
latex_documents = [("index", "pdflinks.tex", "PDF links", "zdocs", "howto")]
# What zdocs_conf sets from the registry: the peers in the PDF set.
zdocs_pdf_peers = {
    "https://docs.example.org/html/requirement-specification": "Requirement-Specification_1.2.pdf"
}

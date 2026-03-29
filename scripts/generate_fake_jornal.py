"""
OstraClaw — Gerador de PDF de Teste Falso (Fase 4)
Cria um PDF falso para testar a detecção do sistema.

Uso: python scripts/generate_fake_jornal.py
"""
from pathlib import Path
import zlib


def create_fake_pdf(output_path: Path) -> None:
    """
    Cria um PDF sintetico com metadados suspeitos (criado no Word)
    e conteudo generico sem as marcas obrigatorias de um Diario Oficial.
    """
    # Conteudo PDF sem palavras-chave de jornal oficial
    page_content = (
        b"q\n"
        b"BT\n"
        b"/F1 12 Tf\n"
        b"50 750 Td\n"
        b"(DOCUMENTO CORPORATIVO INTERNO) Tj\n"
        b"0 -20 Td\n"
        b"(Setor: Recursos Humanos - Confidencial) Tj\n"
        b"0 -20 Td\n"
        b"(Data: 2025-12-01) Tj\n"
        b"0 -20 Td\n"
        b"(Assunto: Comunicado de Reuniao) Tj\n"
        b"0 -40 Td\n"
        b"/F1 10 Tf\n"
        b"(Por meio deste comunicado, informamos que a reuniao anual) Tj\n"
        b"0 -15 Td\n"
        b"(de planejamento estrategico sera realizada na proxima semana.) Tj\n"
        b"0 -15 Td\n"
        b"(Favor confirmar presenca com a secretaria.) Tj\n"
        b"0 -40 Td\n"
        b"(Atenciosamente,) Tj\n"
        b"0 -15 Td\n"
        b"(Departamento Administrativo) Tj\n"
        b"ET\n"
        b"Q"
    )

    stream_data = zlib.compress(page_content)
    stream_len = len(stream_data)

    # Montar o PDF em partes (sem f-strings com bytes misturados)
    header = (
        f"%PDF-1.4\n"
        f"1 0 obj\n"
        f"<< /Type /Catalog /Pages 2 0 R >>\n"
        f"endobj\n\n"
        f"2 0 obj\n"
        f"<< /Type /Pages /Kids [3 0 R] /Count 1 >>\n"
        f"endobj\n\n"
        f"3 0 obj\n"
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]\n"
        f"   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\n"
        f"endobj\n\n"
        f"4 0 obj\n"
        f"<< /Length {stream_len} /Filter /FlateDecode >>\n"
        f"stream\n"
    ).encode("latin-1")

    footer = (
        b"\nendstream\n"
        b"endobj\n\n"
        b"5 0 obj\n"
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\n"
        b"endobj\n\n"
        b"6 0 obj\n"
        b"<< /Title (Comunicado Interno RH)\n"
        b"   /Author (Joao da Silva)\n"
        b"   /Creator (Microsoft Word 2021)\n"
        b"   /Producer (Microsoft Word for Microsoft 365)\n"
        b"   /CreationDate (D:20251201120000)\n"
        b"   /ModDate (D:20251202183045)\n"
        b"   /Keywords (rh, reuniao, interno) >>\n"
        b"endobj\n\n"
        b"xref\n"
        b"0 7\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000058 00000 n \n"
        b"0000000115 00000 n \n"
        b"0000000266 00000 n \n"
        b"0000000420 00000 n \n"
        b"0000000498 00000 n \n\n"
        b"trailer\n"
        b"<< /Size 7 /Root 1 0 R /Info 6 0 R >>\n"
        b"startxref\n"
        b"700\n"
        b"%%EOF"
    )

    pdf_bytes = header + stream_data + footer
    output_path.write_bytes(pdf_bytes)

    print(f"PDF falso criado: {output_path}")
    print("  Creator: Microsoft Word 2021")
    print("  Sem palavras-chave de Diario Oficial")
    print("  Deve ser detectado como FRAUD pelo OstraClaw")


if __name__ == "__main__":
    out = Path(__file__).parent.parent / "data" / "raw" / "FAKE_jornal_suspeito.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    create_fake_pdf(out)

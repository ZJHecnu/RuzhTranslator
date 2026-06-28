"""TMX (Translation Memory eXchange) format parser.

Supports TMX 1.4 specification for import/export of translation memories.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree as ET


def parse_tmx(file_path: str) -> list[dict]:
    """Parse a TMX file and return translation unit pairs.

    Args:
        file_path: Path to the .tmx file.

    Returns:
        List of dicts with keys: source_text, target_text, source_lang, target_lang.
    """
    tree = ET.parse(file_path)
    root = tree.getroot()

    # Detect namespace if present
    ns_match = re.match(r"\{(.+)\}", root.tag)
    ns = f"{{{ns_match.group(1)}}}" if ns_match else ""

    # Get language from header
    header = root.find(f"{ns}header")
    srclang = header.get("srclang", "ru") if header is not None else "ru"

    units = []
    body = root.find(f"{ns}body")
    if body is None:
        return units

    for tu in body.findall(f"{ns}tu"):
        tuvs = tu.findall(f"{ns}tuv")
        source_text = ""
        target_text = ""
        target_lang = ""
        seen_source = False

        for tuv in tuvs:
            xml_ns = "http://www.w3.org/XML/1998/namespace"
            lang = tuv.get(f"{{{xml_ns}}}lang", tuv.get("lang", ""))

            seg = tuv.find(f"{ns}seg")
            text = "".join(seg.itertext()).strip() if seg is not None else "".join(tuv.itertext()).strip()

            # Assign: if this is the first tuv, it's source; second is target
            # (handles case where srclang in header doesn't match actual tuv languages)
            if not seen_source:
                source_text = text
                seen_source = True
            else:
                target_text = text
                target_lang = lang

        if source_text:
            units.append({
                "source_text": source_text,
                "target_text": target_text,
                "source_lang": srclang,
                "target_lang": target_lang or "zh-CN",
            })

    return units


def export_tmx(
    pairs: list[dict],
    output_path: str,
    source_lang: str = "ru",
    target_lang: str = "zh-CN",
) -> None:
    """Export translation pairs to TMX 1.4 format.

    Args:
        pairs: List of dicts with 'source_text' and 'target_text' keys.
        output_path: Output .tmx file path.
        source_lang: Source language code.
        target_lang: Target language code.
    """
    tmx_ns = "http://www.lisa.org/tmx14"
    xml_ns = "http://www.w3.org/XML/1998/namespace"

    root = ET.Element("tmx", {"version": "1.4"})
    header = ET.SubElement(
        root,
        "header",
        {
            "creationtool": "RuzhTranslator",
            "creationtoolversion": "0.1.0",
            "segtype": "sentence",
            "o-tmf": "RuzhTranslator",
            "adminlang": "en-US",
            "srclang": source_lang,
            "datatype": "plaintext",
        },
    )
    body = ET.SubElement(root, "body")

    for pair in pairs:
        tu = ET.SubElement(body, "tu")
        # Source
        tuv_src = ET.SubElement(tu, "tuv", {f"{{{xml_ns}}}lang": source_lang})
        seg_src = ET.SubElement(tuv_src, "seg")
        seg_src.text = pair.get("source_text", "")
        # Target
        tuv_tgt = ET.SubElement(tu, "tuv", {f"{{{xml_ns}}}lang": target_lang})
        seg_tgt = ET.SubElement(tuv_tgt, "seg")
        seg_tgt.text = pair.get("target_text", "")

    # Pretty-print
    ET.indent(root, space="  ")

    tree = ET.ElementTree(root)
    tree.write(
        output_path,
        encoding="utf-8",
        xml_declaration=True,
    )


def import_tmx_to_db(file_path: str, session, project_id: str = "") -> list:
    """Import a TMX file into the database.

    Args:
        file_path: Path to the .tmx file.
        session: SQLAlchemy session.
        project_id: Optional project ID to associate entries with.

    Returns:
        List of created TranslationMemoryEntry instances.
    """
    from ruzh_translator.models.tm import TranslationMemoryEntry

    units = parse_tmx(file_path)
    entries = []
    for unit in units:
        entry = TranslationMemoryEntry(
            source_text=unit["source_text"],
            target_text=unit["target_text"],
            source_lang=unit.get("source_lang", "ru"),
            target_lang=unit.get("target_lang", "zh-CN"),
            project_id=project_id,
        )
        session.add(entry)
        entries.append(entry)
    session.commit()
    return entries

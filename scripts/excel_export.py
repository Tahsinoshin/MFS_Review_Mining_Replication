"""Write the sample sets into one formatted Excel workbook (one sheet per set)."""

from datetime import datetime

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.table import Table, TableStyleInfo

HEADER_FILL = PatternFill("solid", fgColor="1F3864")
HEADER_FONT = Font(bold=True, color="FFFFFF")
TITLE_FONT = Font(bold=True, size=14)
SECTION_FONT = Font(bold=True, size=11, color="1F3864")
TEXT_FONT = Font(name="Nirmala UI", size=10)   # ships with Windows and renders Bangla script
WRAP_TOP = Alignment(wrap_text=True, vertical="top")
TOP = Alignment(vertical="top")

WIDTHS = {"text": 90, "review_id": 38, "reply_text": 60, "note": 30, "manual_lang_group": 20}
DATE_COLUMNS = {"review_date_utc"}


def _safe(value):
    """Make a value storable by openpyxl: drop control characters, keep NaN as blank."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return ILLEGAL_CHARACTERS_RE.sub("", value)
    if hasattr(value, "item"):  # numpy scalar -> Python scalar
        return value.item()
    return value


def write_frame(wb: Workbook, title: str, df: pd.DataFrame, table_name: str,
                text_columns: tuple[str, ...] = ("text",)) -> None:
    ws = wb.create_sheet(title)
    ws.append(list(df.columns))
    for row in df.itertuples(index=False):
        ws.append([_safe(v) for v in row])

    for idx, col in enumerate(df.columns, start=1):
        letter = get_column_letter(idx)
        header = ws.cell(row=1, column=idx)
        header.fill, header.font = HEADER_FILL, HEADER_FONT
        header.alignment = Alignment(vertical="center", wrap_text=True)

        sample = [len(str(v)) for v in df[col].head(200) if v is not None]
        ws.column_dimensions[letter].width = WIDTHS.get(col, min(max([len(col), *sample]) + 2, 24))

        for (cell,) in ws.iter_rows(min_row=2, min_col=idx, max_col=idx):
            # A review that starts with "=" must stay text, not become a formula.
            if cell.data_type == "f":
                cell.data_type = "s"
            if col in text_columns:
                cell.font, cell.alignment = TEXT_FONT, WRAP_TOP
            else:
                cell.alignment = TOP
            if col in DATE_COLUMNS:
                cell.number_format = "yyyy-mm-dd hh:mm"

    ws.freeze_panes = "B2"
    if len(df):
        ref = f"A1:{get_column_letter(len(df.columns))}{len(df) + 1}"
        table = Table(displayName=table_name, ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleLight9", showRowStripes=True)
        ws.add_table(table)


def add_lang_check_tools(wb: Workbook, title: str, df: pd.DataFrame, groups: list[str]) -> None:
    """Drop-down for the manual label plus live agreement / error-rate formulas."""
    ws = wb[title]
    cols = list(df.columns)
    auto_col = get_column_letter(cols.index("lang_group") + 1)
    manual_col = get_column_letter(cols.index("manual_lang_group") + 1)
    last = len(df) + 1

    dv = DataValidation(type="list", formula1='"' + ",".join(groups) + '"', allow_blank=True)
    dv.error, dv.errorTitle = "Pick one of the listed language groups.", "Invalid label"
    ws.add_data_validation(dv)
    dv.add(f"{manual_col}2:{manual_col}{last}")

    label_col = get_column_letter(len(cols) + 2)
    value_col = get_column_letter(len(cols) + 3)
    manual = f"{manual_col}2:{manual_col}{last}"
    auto = f"{auto_col}2:{auto_col}{last}"
    ws[f"{label_col}1"] = "Tagging check"
    ws[f"{label_col}1"].font = SECTION_FONT
    rows = [
        ("Checked", f"=COUNTA({manual})"),
        ("Disagree with auto tag", f'=SUMPRODUCT(({manual}<>"")*({manual}<>{auto}))'),
        ("Error rate", f'=IF({value_col}2=0,"",{value_col}3/{value_col}2)'),
    ]
    for i, (label, formula) in enumerate(rows, start=2):
        ws[f"{label_col}{i}"] = label
        ws[f"{value_col}{i}"] = formula
    ws[f"{value_col}4"].number_format = "0.0%"
    ws.column_dimensions[label_col].width = 24


def write_info_sheet(wb: Workbook, title: str, blocks: list) -> None:
    """Write a sheet of headings, key/value lines, paragraphs and small tables.

    blocks: ("title", str) | ("section", str) | ("kv", [(key, value), ...])
            | ("text", str) | ("table", DataFrame) | ("blank", None)
    """
    ws = wb.create_sheet(title)
    r = 1
    for kind, payload in blocks:
        if kind == "title":
            ws.cell(row=r, column=1, value=payload).font = TITLE_FONT
            r += 1
        elif kind == "section":
            r += 1
            ws.cell(row=r, column=1, value=payload).font = SECTION_FONT
            r += 1
        elif kind == "kv":
            for key, value in payload:
                ws.cell(row=r, column=1, value=key).font = Font(bold=True)
                cell = ws.cell(row=r, column=2, value=_safe(value))
                cell.alignment = Alignment(wrap_text=True, vertical="top")
                r += 1
        elif kind == "text":
            cell = ws.cell(row=r, column=1, value=payload)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=8)
            ws.row_dimensions[r].height = 15 * max(1, len(payload) // 120 + 1)
            r += 1
        elif kind == "table":
            df = payload
            for c, name in enumerate(df.columns, start=1):
                cell = ws.cell(row=r, column=c, value=str(name))
                cell.fill, cell.font = HEADER_FILL, HEADER_FONT
            for row in df.itertuples(index=False):
                r += 1
                for c, v in enumerate(row, start=1):
                    ws.cell(row=r, column=c, value=_safe(v))
            r += 1
        elif kind == "blank":
            r += 1
    ws.column_dimensions["A"].width = 30
    for c in range(2, 12):
        ws.column_dimensions[get_column_letter(c)].width = 16
    ws.column_dimensions["B"].width = 22


def new_workbook() -> Workbook:
    wb = Workbook()
    wb.remove(wb.active)
    wb.properties.title = "MFS review samples"
    wb.properties.created = datetime.now()
    return wb

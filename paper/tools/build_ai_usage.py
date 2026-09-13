#!/usr/bin/env python3
"""根据参赛队确认的使用事实，生成中文 AI 工具使用详情 PDF。"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "attachments" / "AI工具使用详情.pdf"

# 复用论文自带字体，PDF 内嵌所用字形，无须系统另装中文字体。
pdfmetrics.registerFont(TTFont("UsageSong", ROOT / "paper/fonts/simsun.ttc"))
pdfmetrics.registerFont(TTFont("UsageKai", ROOT / "paper/fonts/simkai.ttf"))

body_style = ParagraphStyle(
    "body", fontName="UsageSong", fontSize=11.5, leading=19.5,
    alignment=TA_JUSTIFY, firstLineIndent=23, spaceAfter=8,
    wordWrap="CJK", textColor=colors.black,
)
title_style = ParagraphStyle(
    "title", parent=body_style, fontSize=18, leading=27,
    alignment=TA_CENTER, firstLineIndent=0, spaceAfter=19,
)
heading_style = ParagraphStyle(
    "heading", parent=body_style, fontName="UsageKai", fontSize=13,
    leading=21, firstLineIndent=0, spaceBefore=8, spaceAfter=5,
    keepWithNext=True,
)


def paragraph(text: str) -> Paragraph:
    return Paragraph(text, body_style)


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("UsageSong", 9)
    canvas.drawCentredString(A4[0] / 2, 17 * mm, str(doc.page))
    canvas.restoreState()


story = [
    Paragraph("AI工具使用详情", title_style),
    paragraph("本参赛队在竞赛过程中使用了AI工具，主要用于编程调试、写作排版。具体使用情况如下。"),
    Paragraph("一、所用工具名称与型号", heading_style),
    paragraph("ChatGPT 6 Astra；DeepSeek V41 Flash。"),
    Paragraph("二、具体使用目的和环节", heading_style),
    paragraph("编程调试：在队员已有建模思路、人工公式推导和预期算法的基础上，辅助实现与调试程序；部分环节由队员直接提供人工编写的代码，请AI作局部微调。"),
    paragraph("写作排版：论文框架由队员人工组织，AI依据已有内容辅助优化语言表述与排版。"),
    Paragraph("三、主要提示方式与使用过程", heading_style),
    paragraph("队员向AI说明现有建模思路、人工推导的公式、预期算法及具体实现要求，并按需要提供已有代码。程序出现错误时，围绕错误和预期行为进行多轮对话，逐步调整至可运行，再核对程序实现与论文所述模型、算法是否一致。"),
    paragraph("在论文整理环节，队员提供已组织的论文框架和已有内容，由AI提出写作与排版调整，队员据此完成文稿整理。"),
    Paragraph("四、对AI输出的采纳、人工修改与核验", heading_style),
    paragraph("编程环节采纳了AI辅助给出的部分程序实现、调试修改与局部调整。当AI实现与队员建模思路或预期算法不一致时，相关代码由队员人工调试和修正，并对照论文中的模型与算法说明检查一致性。"),
    paragraph("队员在原实验阶段人工完成模拟测试、演练和正式测试，并对代码和数据进行人工核验。"),
]

document = SimpleDocTemplate(
    str(OUTPUT), pagesize=A4, leftMargin=25 * mm, rightMargin=25 * mm,
    topMargin=24 * mm, bottomMargin=25 * mm,
    title="AI工具使用详情", author="", subject="编程调试与写作排版的AI工具使用说明",
    creator="", pageCompression=1,
)
document.build(story, onFirstPage=footer, onLaterPages=footer)
print(OUTPUT)

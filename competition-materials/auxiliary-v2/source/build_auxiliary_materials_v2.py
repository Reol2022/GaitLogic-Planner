"""Build GaitLogic competition auxiliary-material PDFs from checked-in evidence.

The generated package contains only formal PDFs.  This script deliberately
does not read environment files, databases, provider responses, or private
competition assets.  All numbers in the documents are reproduced from the
public project evaluation reports cited in the material itself.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from PIL import Image as PILImage, ImageDraw, ImageFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "competition-materials" / "auxiliary-v2"
SOURCE = OUT / "source"
DERIVED = SOURCE / "derived-assets"
ASSETS = ROOT / "docs" / "assets"
IMAGES = ROOT / "docs" / "images"
W, H = A4
TEAM = "做梦想达一级"
PROJECT = "GaitLogic 跑者训练智能体"


def fonts() -> None:
    pdfmetrics.registerFont(TTFont("SimSun", r"C:\Windows\Fonts\simsun.ttc", subfontIndex=0))
    pdfmetrics.registerFont(TTFont("TimesNewRoman", r"C:\Windows\Fonts\times.ttf"))


def make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "cover": ParagraphStyle("cover", parent=base["Title"], fontName="SimSun", fontSize=22, leading=31, alignment=TA_CENTER, textColor=colors.black),
        "subcover": ParagraphStyle("subcover", parent=base["Normal"], fontName="SimSun", fontSize=12, leading=20, alignment=TA_CENTER, textColor=colors.black),
        "h1": ParagraphStyle("h1", parent=base["Heading1"], fontName="SimSun", fontSize=15, leading=22, textColor=colors.black, spaceBefore=3, spaceAfter=7),
        "h2": ParagraphStyle("h2", parent=base["Heading2"], fontName="SimSun", fontSize=11.5, leading=17, textColor=colors.black, spaceBefore=4, spaceAfter=4),
        "body": ParagraphStyle("body", parent=base["BodyText"], fontName="SimSun", fontSize=11.2, leading=18.4, alignment=TA_JUSTIFY, firstLineIndent=22, textColor=colors.black, spaceAfter=6),
        "body0": ParagraphStyle("body0", parent=base["BodyText"], fontName="SimSun", fontSize=10.8, leading=17.0, alignment=TA_JUSTIFY, textColor=colors.black, spaceAfter=5),
        "small": ParagraphStyle("small", parent=base["BodyText"], fontName="SimSun", fontSize=8.8, leading=12.0, textColor=colors.black),
        "cap": ParagraphStyle("cap", parent=base["BodyText"], fontName="SimSun", fontSize=9.2, leading=13.5, alignment=TA_CENTER, textColor=colors.black, spaceBefore=4, spaceAfter=6),
        "table": ParagraphStyle("table", parent=base["BodyText"], fontName="SimSun", fontSize=8.5, leading=11.8, textColor=colors.black),
        "note": ParagraphStyle("note", parent=base["BodyText"], fontName="SimSun", fontSize=9.6, leading=14.6, alignment=TA_JUSTIFY, textColor=colors.black, spaceAfter=5),
    }


S: dict[str, ParagraphStyle]


def p(text: str, style: str = "body") -> Paragraph:
    return Paragraph(text, S[style])


def bullets(items: list[str]) -> list[Paragraph]:
    return [p("• " + item, "body0") for item in items]


def tbl(headers: list[str], rows: list[list[str]], widths: list[float]) -> Table:
    values = [[p(x, "table") for x in headers]] + [[p(x, "table") for x in row] for row in rows]
    result = Table(values, colWidths=widths, repeatRows=1, hAlign="LEFT")
    result.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
        ("LINEBELOW", (0, 0), (-1, 0), 0.9, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return result


def footer(canvas, doc) -> None:
    canvas.saveState()
    canvas.setStrokeColor(colors.black)
    canvas.line(1.8 * cm, 1.35 * cm, W - 1.8 * cm, 1.35 * cm)
    canvas.setFont("SimSun", 8)
    canvas.drawString(1.8 * cm, 0.92 * cm, f"第八届中国研究生人工智能创新大赛  |  {PROJECT}  |  团队：{TEAM}")
    canvas.drawRightString(W - 1.8 * cm, 0.92 * cm, f"第 {doc.page} 页")
    canvas.restoreState()


def cover(title: str, subtitle: str) -> list:
    return [
        Spacer(1, 4.0 * cm), p(title, "cover"), Spacer(1, 0.45 * cm), p(subtitle, "subcover"),
        Spacer(1, 1.1 * cm), p(f"项目名称：{PROJECT}", "subcover"), p(f"团队名称：{TEAM}", "subcover"),
        Spacer(1, 6.2 * cm), p("其他辅助材料", "subcover"), PageBreak(),
    ]


def image(path: Path, max_w: float, max_h: float) -> Image:
    obj = Image(str(path))
    scale = min(max_w / obj.imageWidth, max_h / obj.imageHeight)
    obj.drawWidth = obj.imageWidth * scale
    obj.drawHeight = obj.imageHeight * scale
    return obj


class BoxFlow(Flowable):
    def __init__(self, groups: list[tuple[str, list[str]]], width: float = 16.5 * cm, height: float = 9.0 * cm) -> None:
        self.groups, self.width, self.height = groups, width, height

    def draw(self) -> None:
        c = self.canv
        count = len(self.groups)
        row_h, gap = 42, 15
        y = self.height - row_h
        for i, (title, items) in enumerate(self.groups):
            c.setFont("SimSun", 9)
            c.rect(0, y, self.width, row_h, stroke=1, fill=0)
            c.setFont("SimSun", 9)
            c.drawString(7, y + row_h - 13, title)
            inner_y = y + 9
            n = len(items)
            gap_x = 8
            bw = (self.width - 14 - gap_x * (n - 1)) / n
            for j, label in enumerate(items):
                x = 7 + j * (bw + gap_x)
                c.rect(x, inner_y, bw, 15, stroke=1, fill=0)
                c.setFont("SimSun", 7.2)
                c.drawCentredString(x + bw / 2, inner_y + 4.5, label)
            if i < count - 1:
                mid = self.width / 2
                c.line(mid, y - 2, mid, y - gap + 4)
                c.line(mid, y - gap + 4, mid - 3, y - gap + 8)
                c.line(mid, y - gap + 4, mid + 3, y - gap + 8)
            y -= row_h + gap


class BarChart(Flowable):
    def __init__(self, title: str, values: list[float], labels: list[str], suffix: str = "%", width: float = 16.5 * cm, height: float = 6.0 * cm) -> None:
        self.title, self.values, self.labels, self.suffix = title, values, labels, suffix
        self.width, self.height = width, height

    def draw(self) -> None:
        c = self.canv
        left, bottom, top = 38, 24, 26
        chart_h, chart_w = self.height - bottom - top, self.width - left - 10
        c.setFont("SimSun", 9)
        c.drawString(0, self.height - 11, self.title)
        c.line(left, bottom, left, bottom + chart_h)
        c.line(left, bottom, left + chart_w, bottom)
        maxv = 100.0
        for tick in (0, 25, 50, 75, 100):
            y = bottom + chart_h * tick / maxv
            c.setFont("TimesNewRoman", 6.5)
            c.drawRightString(left - 4, y - 2, str(tick))
            c.setDash(1, 2); c.line(left, y, left + chart_w, y); c.setDash()
        step = chart_w / len(self.values)
        for i, value in enumerate(self.values):
            x = left + i * step + step * .22
            bw = step * .56
            bh = chart_h * value / maxv
            c.setFillColor(colors.black if i == len(self.values) - 1 else colors.lightgrey)
            c.rect(x, bottom, bw, bh, stroke=1, fill=1)
            c.setFillColor(colors.black)
            c.setFont("TimesNewRoman", 6.7)
            c.drawCentredString(x + bw / 2, bottom + bh + 4, f"{value:.2f}{self.suffix}")
            c.setFont("TimesNewRoman", 7)
            c.drawCentredString(x + bw / 2, bottom - 11, self.labels[i])


class HorizontalBarChart(Flowable):
    """Formal black-and-white horizontal bars; axes always start at zero."""
    def __init__(self, title: str, labels: list[str], values: list[float], max_value: float, suffix: str, width: float = 16.5 * cm, height: float = 8.4 * cm) -> None:
        self.title, self.labels, self.values = title, labels, values
        self.max_value, self.suffix, self.width, self.height = max_value, suffix, width, height

    def draw(self) -> None:
        c = self.canv
        left, right, top, bottom = 128, 22, 24, 24
        chart_w = self.width - left - right
        row_h = (self.height - top - bottom) / len(self.labels)
        c.setFont("SimSun", 9); c.drawString(0, self.height - 11, self.title)
        c.line(left, bottom, left + chart_w, bottom)
        for tick in range(0, int(self.max_value) + 1):
            if self.max_value == 5 or tick % 20 == 0:
                x = left + chart_w * tick / self.max_value
                c.setDash(1, 2); c.line(x, bottom, x, self.height - top); c.setDash()
                c.setFont("TimesNewRoman", 6.5); c.drawCentredString(x, bottom - 10, str(tick))
        for i, (label, value) in enumerate(zip(self.labels, self.values)):
            y = self.height - top - (i + 1) * row_h + row_h * .25
            bh = row_h * .48
            c.setFont("SimSun", 7.4); c.drawRightString(left - 6, y + 2, label)
            c.setFillColor(colors.black if i == 0 else colors.lightgrey)
            c.rect(left, y, chart_w * value / self.max_value, bh, stroke=1, fill=1)
            c.setFillColor(colors.black); c.setFont("TimesNewRoman", 7)
            c.drawString(left + chart_w * value / self.max_value + 4, y + 2, f"{value:.2f}{self.suffix}" if self.max_value == 5 else f"{int(value)}{self.suffix}")


class StepFlow(Flowable):
    def __init__(self, labels: list[str], width: float = 16.5 * cm, height: float = 3.0 * cm) -> None:
        self.labels, self.width, self.height = labels, width, height

    def draw(self) -> None:
        c = self.canv; n = len(self.labels); gap = 10; bw = (self.width - gap*(n-1))/n; bh = 27; y = (self.height-bh)/2
        for i, label in enumerate(self.labels):
            x = i*(bw+gap); c.rect(x,y,bw,bh,stroke=1,fill=0); c.setFont("SimSun",7.6)
            chunks = label.split("\n")
            for j, chunk in enumerate(chunks): c.drawCentredString(x+bw/2,y+bh/2+3-j*10,chunk)
            if i<n-1:
                c.line(x+bw+2,y+bh/2,x+bw+gap-3,y+bh/2)
                c.line(x+bw+gap-3,y+bh/2,x+bw+gap-7,y+bh/2+3); c.line(x+bw+gap-3,y+bh/2,x+bw+gap-7,y+bh/2-3)


def annotate_assets() -> dict[str, Path]:
    """Create derived, non-sensitive callout images without changing source screenshots."""
    DERIVED.mkdir(parents=True, exist_ok=True)
    mappings = {
        "coach_today": (ASSETS / "coach-agent" / "coach-rag-today.png", [(28, 115, "① 规则建议"), (28, 210, "② 训练事实"), (28, 390, "③ AI解释"), (28, 570, "④ 知识依据")]),
        "weekly_review": (IMAGES / "weekly-review1.png", [(36, 100, "① 本周完成情况"), (36, 270, "② 周训练分析"), (36, 450, "③ 下一步建议")]),
        "weekly_proposal": (IMAGES / "weekly-review3.png", [(35, 105, "① 调整前后对比"), (35, 350, "② 用户确认入口")]),
    }
    result: dict[str, Path] = {}
    font_path = r"C:\Windows\Fonts\msyh.ttc"
    font = ImageFont.truetype(font_path, 24, index=0)
    for name, (src, marks) in mappings.items():
        target = DERIVED / f"{name}.png"
        im = PILImage.open(src).convert("RGB")
        draw = ImageDraw.Draw(im)
        for x, y, text in marks:
            box = draw.textbbox((x, y), text, font=font)
            draw.rectangle((box[0]-7, box[1]-5, box[2]+7, box[3]+5), fill="white", outline="black", width=2)
            draw.text((x, y), text, fill="black", font=font)
        im.save(target)
        result[name] = target
    # Garmin source has account details near the header.  Crop below the account area and add an explicit desensitization label.
    garmin_src = IMAGES / "garmin.png"; garmin_target = DERIVED / "garmin_sync_desensitized.png"
    g = PILImage.open(garmin_src).convert("RGB")
    g = g.crop((0, int(g.height * 0.30), g.width, g.height))
    d = ImageDraw.Draw(g); d.rectangle((10, 10, 250, 48), fill="white", outline="black", width=2); d.text((20, 16), "设备同步界面（已脱敏）", fill="black", font=font)
    g.save(garmin_target); result["garmin"] = garmin_target
    return result


def build(filename: str, story: list) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / filename
    doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=1.85*cm, rightMargin=1.85*cm, topMargin=1.55*cm, bottomMargin=1.75*cm, title=filename)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return target


def technical() -> Path:
    st = cover("GaitLogic 技术可行性与系统架构说明", "面向跑者训练管理闭环的可运行智能体系统")
    st += [p("一、问题场景与项目定位", "h1"), p("长期规律训练的跑者在一周内会同时面对原定训练计划、实际完成偏差、高强度课与长距离课、主观疲劳、设备恢复指标和跑量变化。真正困难的不是简单汇总“跑了多少公里”，而是将这些来源不同、完整度不同的数据组织成可理解的训练事实，并回答“当前训练状态意味着什么”“今天是否仍适合执行计划”“本周是否需要为下一阶段做准备”。GaitLogic 以训练管理而非医疗诊断为定位，建立计划、执行、状态、解释与确认相互衔接的闭环。"), p("系统将确定性训练规则与模型解释分开：训练事实、风险提示和是否可判断的边界由服务端规则控制；模型仅在受控工具和公开训练知识的范围内组织解释。涉及正式训练计划的改变，系统只生成可审查方案，用户确认后还要由服务端进行二次校验。", "body"),
           p("二、从训练数据到正式计划的完整闭环", "h1"), BoxFlow([("数据层", ["训练计划", "训练日志", "设备同步", "Runner State", "主观反馈"]), ("事实层", ["统一训练事实", "数据质量", "训练负荷", "执行一致性"]), ("决策层", ["训练规则", "充分性判断", "证据检查", "受控补证", "训练知识"]), ("AI解释层", ["Coach", "周复盘", "方案设计"]), ("安全与执行层", ["Validator", "Proposal", "用户确认", "正式计划"])], height=10.3*cm), p("图 1  GaitLogic 的分层训练管理闭环。每一层都有独立职责：事实层不直接生成语言结论，解释层不直接写入正式计划。", "cap"), PageBreak(),
           p("三、AI Coach 完整调用链", "h1"), StepFlow(["用户问题", "意图识别", "读取训练事实", "判断可用范围", "规则与知识", "AI解释", "安全校验", "最终结果"], height=3.2*cm), p("图 2  Coach 的受控请求链路。意图识别决定可用工具；事实读取不允许客户端指定其他用户；数据充分性判断把“可以分析、受限分析、无法判断”分开；训练知识用于解释原则，不能替代个人事实。", "cap"),
           tbl(["步骤", "作用", "可解释输出"], [["意图与工具", "识别今日建议、状态解释或一般训练问题，并只开放只读工具。", "工具名称、调用状态。"], ["训练事实", "从计划、日志、状态和授权设备数据中读取结构化事实。", "关键依据、数据覆盖。"], ["规则与知识", "规则给出决策边界；检索给出训练原则来源。", "风险提示、知识引用。"], ["校验与降级", "拒绝越权、无依据或不安全表达；外部模型不可用时退回规则说明。", "限制提示、降级状态。"]], [2.4*cm, 8.4*cm, 5.5*cm]),
           p("四、Weekly Review 与计划调整闭环", "h1"), StepFlow(["本周计划", "实际训练", "状态与负荷", "Weekly Review", "调整方案", "用户确认", "服务端校验", "正式计划"], height=3.2*cm), p("图 3  周复盘不是直接改课表。系统先汇总本周完成、负荷、恢复与状态，再产生下一阶段建议。Proposal 仅是待确认方案；批准前不能写入正式计划，批准后仍受版本、所有权、规则和事务校验约束。", "cap"), tbl(["检查点", "系统如何处理", "用户可理解的结果"], [["周训练事实", "分开读取计划完成、训练量、频次、关键课、恢复与阶段信息。", "看到本周哪些事实参与了复盘。"], ["部分事实", "按域判断可用、受限和阻塞，不把单个缺失字段扩大成全局结论。", "看到分析范围与限制原因。"], ["方案生成", "方案只能基于当前事实、规则和可验证的版本状态生成。", "看到调整前后差异与理由。"], ["正式应用", "需要用户确认，并在写入前再次做版本、所有权和规则检查。", "确认前不改变正式训练计划。"]], [3.0*cm, 7.2*cm, 6.2*cm]), PageBreak(),
           p("五、数据来源、用途与可信边界", "h1"), tbl(["来源", "数据类型", "使用目的", "可信边界"], [["训练计划", "周期、训练安排、目标", "识别今日计划与周计划基线", "计划不等于实际完成。"], ["训练日志", "距离、时长、主观记录", "汇总训练负荷与执行情况", "缺失字段仅作为缺失处理。"], ["授权设备同步", "活动与恢复相关字段", "补充训练事实与恢复线索", "仅在授权范围内使用。"], ["Runner State", "状态、证据、限制", "说明近期训练状态", "不作医学诊断。"], ["训练知识", "来源、章节、版本", "解释一般训练原则", "不证明个人身体状态。"], ["模型与向量服务", "语言解释、向量化、重排序", "在服务端受控链路中使用", "不获得正式计划写权限。"]], [2.4*cm, 3.3*cm, 4.9*cm, 5.7*cm]),
           p("六、技术选型与可行性", "h1"), tbl(["技术", "承担职责", "选择理由"], [["FastAPI", "后端 API 与身份边界", "Python 生态、类型校验和服务接口组织方便。"], ["SQLAlchemy + MySQL", "核心业务持久化", "适合训练计划、日志、状态等结构化数据与事务校验。"], ["LangGraph", "有状态工作流", "适合周复盘、审批与恢复流程中的状态推进。"], ["Qdrant / Exact Store", "向量检索后端", "支持可替换检索实现和版本化索引。"], ["BM25 + 融合 + 重排序", "知识检索质量", "把关键词与语义候选结合，再以候选级排序改善引用。"], ["Vue + TypeScript", "训练管理与解释展示", "适合页面状态、表单和可解释交互。"]], [3.1*cm, 4.3*cm, 8.9*cm]), p("技术选择遵循“业务真相在服务端、模型解释在受控边界、正式写入需用户确认”的原则。数据库承担计划、日志与状态的事务事实；模型服务不被赋予数据所有权或写计划权限；检索组件可替换，因此不会使训练业务逻辑与单一向量后端绑定。", "note"), PageBreak(),
           p("七、部署拓扑与运行边界", "h1"), BoxFlow([("访问层", ["用户浏览器", "Web前端"]), ("服务层", ["Nginx", "FastAPI", "身份校验"]), ("业务与数据层", ["训练服务", "规则引擎", "MySQL"]), ("AI 与检索侧", ["模型 Provider", "Embedding", "Retriever", "Vector Store"]), ("安全保障", ["Validator", "降级", "日志脱敏", "测试回归"])], height=10.3*cm), p("图 4  部署拓扑。常规 CPU 云服务器承载前端、后端、数据库与检索连接；通用模型推理由外部 Provider 提供。索引运行目录不作为 Web 静态资源暴露，配置与访问凭据不写入材料或前端。", "cap"),
           p("八、当前完成度与适用范围", "h1"), *bullets(["已形成包含训练计划、日历、训练日志、设备同步、Runner State、Coach、周复盘和计划调整的 Web 系统闭环。", "已建立固定虚构案例上的智能体消融实验、检索评测和安全回归，详见后续材料。", "系统面向训练管理参考，不替代医生、康复师或专业教练；伤病、疼痛和异常疲劳只提供保守提示。", "当前能力受数据完整度、训练知识覆盖和外部服务可用性影响；界面会保留相应限制说明。"]), PageBreak(),
           p("九、项目原创与第三方技术边界", "h1"), tbl(["类别", "项目内实现", "第三方技术或资料的作用"], [["训练业务与规则", "训练事实建模、充分性判断、Evidence、Proposal 与确认流程。", "公开训练理论仅作为知识来源和解释参考。"], ["智能体安全", "工具白名单、身份注入、Validator、Fallback、只读边界。", "模型 Provider 提供语言生成能力。"], ["检索工程", "Corpus 编排、元数据过滤、引用还原、评测和安全合同。", "向量、关键词与重排序组件提供基础算法能力。"], ["产品界面", "训练管理、状态说明、知识引用与审批交互。", "前端框架提供通用界面能力。"]], [3.3*cm, 7.0*cm, 6.0*cm]), p("参考资料", "h1"), *bullets(["GaitLogic 项目内版本化训练知识语料、系统设计、测试与评测报告。", "Jack Daniels，《Daniels’ Running Formula》相关公开版本的结构化自写总结；不复制受版权保护的大段原文。", "FastAPI、SQLAlchemy、LangGraph、MySQL、Qdrant 与 BM25 等公开技术文档。", "Garmin 公开产品与开发者资料，仅用于说明授权设备数据的来源边界。"]), PageBreak(),
           p("十、关键模块如何协同而不相互越权", "h1"), tbl(["模块", "可以做什么", "明确不能做什么", "与其他模块的关系"], [["Runner State", "基于近期训练事实给出状态、Evidence 与数据限制。", "不诊断疾病，不替代临床判断。", "为 Coach、周复盘提供结构化状态。"], ["Decision Readiness", "判断每个事实域是可用、受限还是阻塞。", "不把任一缺失字段等同于整体不可用。", "为规则、Validator 和界面提供共同口径。"], ["Coach", "回答公开意图范围内的训练问题。", "不直接写入训练计划或访问他人数据。", "只能在规则、工具和知识边界内解释。"], ["Weekly Review", "汇总一周训练计划与实际执行。", "不自动批准调整方案。", "输出事实、限制与可审查建议。"], ["Proposal", "呈现拟议调整并保留确认状态。", "不因模型回答而直接生效。", "应用前再次做所有权、版本和规则校验。"]], [3.0*cm, 4.6*cm, 4.8*cm, 4.7*cm]), p("这种职责拆分使每个模块可独立测试：事实是否正确、规则是否一致、解释是否越界、确认是否发生以及写入是否被授权，均不依赖单一模型输出。", "note"),
           p("十一、工程可靠性设计", "h1"), tbl(["场景", "系统处理", "为什么对训练管理重要"], [["训练数据不完整", "按域给出 READY、PARTIAL 或 BLOCKED 的事实可用性。", "避免将缺少 RPE 等情况夸大成所有结论都不可用。"], ["证据相互冲突", "保留冲突与限制，拒绝被阻塞域确定断言。", "避免单一恢复信号覆盖其他训练事实。"], ["外部模型不可用", "使用确定性 Fallback，保留规则建议。", "核心训练管理不依赖模型始终在线。"], ["检索结果为空", "不伪造知识来源，提示当前没有直接依据。", "引用透明优先于看似完整的回答。"], ["计划并发变化", "应用 Proposal 时检查版本与事务条件。", "避免旧方案覆盖用户之后的真实修改。"]], [3.2*cm, 6.0*cm, 7.2*cm]), PageBreak(),
           p("十二、可验证性与阶段性结论", "h1"), p("GaitLogic 的可行性不只来自技术组件可拼接，还来自可验证的边界：训练事实、充分性判断、知识引用、模型解释、Proposal 和正式计划写入分别有独立合同。项目已形成 Web 端训练管理闭环，并在固定虚构案例上完成智能体、检索和安全回归。产品可在小范围试用中继续验证交互可理解性与数据录入完整度问题。"), tbl(["验证层", "已形成的验证方式", "材料对应位置"], [["业务闭环", "计划、日志、同步、状态、Coach、周复盘与确认的运行界面。", "03 系统功能与运行截图。"], ["智能体机制", "24 案例、6 变体、432 次真实推理调用的聚合对比。", "02 AI 消融实验完整报告。"], ["知识与安全", "Corpus、检索策略、失败分析与固定安全回归。", "04 检索与安全评测说明。"], ["产品验证", "真实产品流程、阶段问题与后续匿名反馈设计。", "05 用户内测与产品验证说明。"]], [3.1*cm, 8.1*cm, 5.2*cm]), p("阶段性结论：项目已经具备完整训练管理与受控智能解释能力；后续重点在于扩大真实使用验证、持续优化部分事实下的可解释性，并保持医疗边界与正式计划写入边界。", "note")]
    return build("01_GaitLogic技术可行性与系统架构说明.pdf", st)


def ablation() -> Path:
    labels = ["A", "B", "C", "D", "E", "F"]
    st = cover("GaitLogic AI 消融实验完整报告", "基于固定虚构训练案例的受控系统对比")
    st += [p("一、实验问题与实验范围", "h1"), p("本实验关注训练智能体在结构化事实、数据缺失和安全边界上的工程表现，而非宣称模型在开放世界训练问题上具有医学或教练级正确性。实验使用 24 个固定虚构训练案例，每个变体对每个案例重复运行 3 次，共形成 432 次真实推理调用。全部调用完成，未出现 Provider 或结构化 Schema 失败。"), tbl(["研究问题", "要验证的机制", "对应观察指标"], [["RQ1", "结构化训练工具是否提升事实一致性？", "事实一致性。"], ["RQ2", "充分性判断是否减少“缺一点数据就全部拒答”？", "部分事实响应、错误整体阻塞。"], ["RQ3", "Evidence Judge 是否提高事实与证据的使用质量？", "事实一致性、被阻塞域幻觉。"], ["RQ4", "Reflect 能否通过受控补证改善部分数据场景？", "部分事实响应、错误整体阻塞。"]], [2.0*cm, 8.4*cm, 5.9*cm]),
           p("二、案例集构成", "h1"), tbl(["真实类别", "数量", "主要测试能力"], [["FACT_QUERY", "3", "读取七日距离、周频次、今日计划等结构化事实。"], ["TRAINING_DECISION", "3", "连续强度、跑量增长、恢复日等训练决策。"], ["PARTIAL_FACTS", "3", "RPE、HRV、睡眠与阶段信息部分缺失。"], ["EVIDENCE_CONFLICT", "3", "恢复信号、训练负荷或周完成情况发生冲突。"], ["REFLECT", "3", "受控补充事实后重新判断。"], ["UNRESOLVABLE_EVIDENCE", "3", "主观 RPE、训练阶段、结构化分段等无法补齐。"], ["WEEKLY_REVIEW", "3", "完整周、部分恢复和关键课不完整的周复盘。"], ["PROPOSAL_SAFETY", "3", "提高跑量/强度、版本冲突的计划写入安全。"]], [4.2*cm, 1.5*cm, 10.6*cm]), PageBreak(),
           p("三、六个 Variant 的能力矩阵", "h1"), tbl(["能力", "A", "B", "C", "D", "E", "F"], [["通用模型回答", "✓", "✓", "✓", "✓", "✓", "✓"], ["结构化工具读取", "—", "✓", "✓", "✓", "✓", "✓"], ["可信事实与规则约束", "—", "—", "✓", "✓", "✓", "✓"], ["Decision Readiness", "—", "—", "—", "✓", "✓", "✓"], ["Evidence Judge", "—", "—", "—", "—", "✓", "✓"], ["受控 Reflect 补证", "—", "—", "—", "—", "—", "✓"], ["Validator 与安全降级", "基础", "基础", "基础", "基础", "基础", "完整链路"]], [5.2*cm, 1.6*cm, 1.6*cm, 1.6*cm, 1.6*cm, 1.6*cm, 1.8*cm]),
           p("四、指标定义：为什么不能只看“回答是否流畅”", "h1"), tbl(["指标", "定义", "为什么重要"], [["事实一致性", "回答中的训练事实与输入事实一致。", "避免把计划、日志或状态说错。"], ["部分事实响应", "部分域可判断时，仍给出受限但有依据的分析。", "避免“缺一项就全拒答”。"], ["错误整体阻塞", "存在有用事实却错误地整体拒答。", "反映系统是否过度保守。"], ["被阻塞域幻觉", "缺少恢复等关键证据仍作确定判断。", "直接对应安全风险。"], ["支持的决策", "结论是否被相应事实与规则支持。", "防止语言解释覆盖确定性边界。"]], [3.1*cm, 6.0*cm, 7.5*cm]), p("示例：当睡眠字段缺失但跑量、计划和执行事实完整时，系统可以对训练负荷作受限解释；若仍断言“已经完全恢复”，则属于被阻塞域的确定性臆断。", "note"), PageBreak(),
           p("五、完整聚合结果", "h1"), tbl(["Variant", "事实一致性", "支持的决策", "部分事实响应", "错误整体阻塞", "被阻塞域幻觉", "平均时长"], [["A 仅模型", "81.16%", "2.17%", "10.26%", "25.64%", "3.70%", "21.01 秒"], ["B 工具+模型", "89.86%", "2.20%", "5.13%", "25.64%", "3.70%", "23.19 秒"], ["C 可信核心", "75.36%", "0.00%", "10.26%", "20.51%", "7.41%", "22.09 秒"], ["D 部分事实", "88.41%", "20.00%", "41.03%", "56.41%", "0.00%", "23.52 秒"], ["E 证据检查", "93.48%", "12.86%", "41.03%", "58.97%", "0.00%", "25.45 秒"], ["F 完整系统", "96.38%", "12.82%", "58.97%", "41.03%", "0.00%", "19.76 秒"]], [2.35*cm, 2.05*cm, 1.85*cm, 2.15*cm, 2.15*cm, 2.15*cm, 2.0*cm]), p("表 1  六种系统配置在固定虚构案例上的聚合结果。平均时长仅是工程观察，不同阻塞与完成路径不完全可比。", "cap"),
           p("六、图表：事实一致性与部分事实响应", "h1"), BarChart("图 1  事实一致性（%）", [81.16,89.86,75.36,88.41,93.48,96.38], labels), Spacer(1, 0.2*cm), BarChart("图 2  部分事实响应（%）", [10.26,5.13,10.26,41.03,41.03,58.97], labels), PageBreak(),
           p("七、图表：过度保守与被阻塞域安全", "h1"), BarChart("图 3  错误整体阻塞（%）；数值越低越好", [25.64,25.64,20.51,56.41,58.97,41.03], labels), Spacer(1, 0.2*cm), BarChart("图 4  被阻塞域幻觉（%）；目标为零", [3.70,3.70,7.41,0.00,0.00,0.00], labels), p("重点结果：从 A 到 F，事实一致性由 81.16% 提升至 96.38%，提高 15.22 个百分点；部分事实响应由 10.26% 提升至 58.97%；被阻塞域幻觉由 3.70% 降至 0.00%。同时，F 的错误整体阻塞仍为 41.03%，说明系统仍需要继续降低不必要的保守拒答。", "note"), PageBreak(),
           p("八、逐层贡献与工程代价", "h1"), tbl(["比较", "新增机制", "观察到的变化", "说明与代价"], [["A → B", "结构化工具读取", "事实一致性 81.16% → 89.86%。", "读取事实减少纯语言猜测，但不自动改善部分事实处理。"], ["C → D", "Decision Readiness", "部分事实响应 10.26% → 41.03%；幻觉降至 0。", "能区分不同事实域，但初期会更保守。"], ["D → E", "Evidence Judge", "事实一致性升至 93.48%；幻觉保持 0。", "证据检查提高安全性，也使错误整体阻塞升至 58.97%。"], ["E → F", "Reflect 受控补证", "部分事实响应升至 58.97%；错误整体阻塞回落至 41.03%。", "只在可受控补充事实时重试，不放宽写入或安全边界。"]], [2.0*cm, 3.2*cm, 4.6*cm, 6.8*cm]),
           p("九、代表性案例摘要", "h1"), tbl(["案例", "已知/缺失事实", "基线倾向", "完整系统行为为何更合理"], [["事实读取：七日跑量", "结构化跑量事实可用。", "仅语言回答可能遗漏或改写数值。", "通过只读工具读取训练事实，再由 Validator 校验。"], ["部分事实：RPE 缺失", "跑量与计划可用；RPE 缺失。", "容易把任一缺失升级为整体无法分析。", "保持可判断域结论，并明确主观疲劳域受限。"], ["证据冲突：恢复信号", "恢复相关线索存在不一致。", "可能选择单一信号做确定结论。", "Evidence Judge 保留冲突与限制，避免强行统一。"], ["Reflect：恢复信息补齐", "首轮必要事实不足；受控补充后可读取。", "首轮阻塞后直接终止。", "仅补充允许的事实，再依据更新后的证据重判。"]], [3.0*cm, 4.3*cm, 3.7*cm, 5.6*cm]), PageBreak(),
           p("十、Full GaitLogic 失败案例分析", "h1"), p("完整系统 F 的错误整体阻塞为 16/39（41.03%）。该结果必须保留：它表明系统已经把被阻塞域幻觉降为零，但仍有部分可分析信息未被充分利用。基于逐案例的真实聚合结果，主要集中在周完成情况冲突、无法取得的主观 RPE、无法取得的结构化分段，以及计划调整安全场景。"), tbl(["实际失败聚集项", "出现次数（3 次重复聚合）", "保守原因"], [["周完成情况冲突", "3", "证据冲突仍容易触发整体保守。"], ["主观 RPE 不可取得", "3", "主观疲劳域无法补足时，边界处理仍偏严。"], ["结构化分段缺失", "3", "计划文本缺少细分结构，部分强度判断不充分。"], ["提高跑量/强度 Proposal", "6", "写入安全场景宁可阻塞，也不越过计划修改边界。"], ["训练阶段不可取得", "1", "阶段相关解释保留限制。"]], [4.4*cm, 3.1*cm, 9.1*cm]), p("评分协议也会影响该指标：Proposal 场景要求对写入安全严格阻塞，因此“分析可继续”不等于“计划修改可继续”。后续工作应优先提升可读事实的域级利用，而不降低 Proposal、用户确认、版本校验与事务边界。", "note"), PageBreak(),
           p("十一、实验结论与限制", "h1"), *bullets(["在本固定虚构案例集上，完整系统主要依靠真实事实、数据充分性判断、证据检查和受控补证取得改进，而不是单纯更换更强模型。", "事实一致性达到 133/138；部分事实响应达到 23/39；被阻塞域幻觉为 0/27。", "固定案例和确定性评分只能验证已定义的事实与安全合同，不等同于长期真实跑者干预研究或开放世界准确率。", "模型服务不支持固定随机种子时，输出具有随机性；本实验已使用每案例三次重复来观察聚合表现。"]), p("参考资料", "h1"), *bullets(["GaitLogic《Competition Ablation Full Results》：24 案例、6 变体、3 次重复的真实调用聚合。", "GaitLogic 公开固定虚构案例集与确定性评分规则。", "模型、工具和知识服务均在服务端受控链路中使用；本材料不保存原始回答、完整交互输入或推理内容。"]), PageBreak(),
           p("十二、运行协议与统计口径", "h1"), tbl(["要素", "实际设置", "为何需要明确"], [["案例", "24 个固定虚构训练案例。", "排除真实用户数据和不可重复的输入差异。"], ["变体", "A 至 F 六种逐层增强结构。", "能观察机制加入前后的行为变化。"], ["重复", "每案例、每变体运行 3 次。", "缓解外部模型输出随机性。"], ["调用总数", "24 × 6 × 3 = 432 次。", "所有调用完成，未见 Provider 或 Schema 失败。"], ["评分", "确定性事实与安全合同。", "不把语言风格好坏混入安全指标。"]], [3.2*cm, 6.7*cm, 6.5*cm]), p("平均时长与平均输出规模同时被记录。完整系统 F 的平均时长为 19.76 秒、平均调用规模为 2807.92；这些工程观察与系统是否被阻塞、是否需要补证等路径有关，不能据此宣称完整系统在任何情况下都更快或更节省。", "note"),
           p("十三、从数字到系统结论", "h1"), tbl(["真实结果", "应如何理解", "不应如何解读"], [["F 事实一致性 96.38%", "在已定义的固定案例上，结构化事实与校验链路提高了对齐程度。", "不等于所有真实跑者问题都达到 96.38% 正确。"], ["F 部分事实响应 58.97%", "更多部分信息场景可给出受限分析。", "不等于每个缺失数据场景都可安全回答。"], ["F 幻觉 0.00%", "被阻塞域没有出现预定义的确定性臆断。", "不代表语言模型永远不会犯错。"], ["F 错误整体阻塞 41.03%", "系统仍然偏保守，存在优化空间。", "不能只挑选正面指标而忽略该问题。"]], [3.3*cm, 6.8*cm, 6.3*cm]), PageBreak(),
           p("十四、面向复现的实验资产边界", "h1"), p("实验的案例集合、结构定义和聚合结果均在项目内版本化保存；材料中仅呈现安全的案例类别、指标与聚合结论。为了保护训练事实和模型交互边界，本报告不包含用户身份、完整交互输入、完整上下文、原始模型回答、推理内容或访问凭据。"), tbl(["可公开说明", "不随材料公开"], [["案例类型、数量、指标定义、Variant 能力矩阵、聚合结果与失败聚集项。", "真实用户训练数据、完整问答、交互输入、上下文、模型原始响应、访问凭据。"], ["固定虚构案例的测试意图与确定性评分范围。", "任何可反向识别用户、训练轨迹或账户身份的信息。"], ["432 次调用已完成、无服务或结构校验失败的聚合事实。", "调用请求的隐私内容与可用于复现凭据的配置信息。"]], [8.0*cm, 8.4*cm]), p("因此，本实验可支持的结论是工程机制在固定虚构案例上的相对表现；产品在真实环境中的长期效果仍需经持续、合规的用户验证。", "note")]
    return build("02_GaitLogic_AI消融实验完整报告.pdf", st)


def screenshots(derived: dict[str, Path]) -> Path:
    st = cover("GaitLogic 系统功能与运行截图", "以脱敏产品界面展示训练管理、智能解释与确认闭环")
    st += [p("使用说明", "h1"), p("本材料按真实用户路径组织现有产品截图。截图仅用于功能说明：不包含账号、邮箱、访问凭据、设备序列号、精确轨迹或后台地址；局部编号和边框仅标示界面区域，不改变原页面含义。训练数据展示用于产品交互说明，不构成医学建议。"),
           p("一、从训练计划到训练事实", "h1"), Table([[image(IMAGES/"training-plan-center.png", 7.8*cm, 11.0*cm), image(IMAGES/"training-calendar.png", 7.8*cm, 11.0*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 1  训练计划中心与训练日历。计划承担“应做什么”的基线，实际训练日志承担“做了什么”的事实；系统不将二者混为一项。", "cap"), PageBreak(),
           p("二、训练日志与设备同步进入事实层", "h1"), Table([[image(IMAGES/"workout-log-edit.png", 8.0*cm, 11.3*cm), image(derived["garmin"], 8.0*cm, 11.3*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 2  训练日志与已脱敏设备同步界面。训练日志可记录实际执行与主观信息；经授权的设备活动进入统一同步链路，再被归入训练事实。同步页面不展示访问凭据或原始敏感载荷。", "cap"),
           p("三、Runner State 与训练准备情况", "h1"), Table([[image(ASSETS/"runner-state"/"runner-state1.png", 7.9*cm, 8.0*cm), image(ASSETS/"training-readiness"/"training-readiness1.png", 7.9*cm, 8.0*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 3  Runner State 与训练准备情况。页面同时呈现状态、证据和数据覆盖，帮助用户区分“已有事实支持的结论”与“尚缺少的输入”。", "cap"), PageBreak(),
           p("四、AI Coach 的入口与输入边界", "h1"), image(ASSETS/"coach-agent"/"coach-overview.png", 16.3*cm, 15.0*cm), p("图 4  AI Coach 入口。用户可选择今日训练建议、解释当前状态或一般训练问题。页面固定提示：建议仅供训练决策参考，不用于医疗诊断，也不会自动修改训练计划。", "cap"),
           p("五、今日训练问题如何走完整流程", "h1"), StepFlow(["用户提问", "读取计划与日志", "规则建议", "AI解释", "知识依据", "限制提示"], height=3.0*cm), p("图 5  今日训练建议的产品路径。规则建议先于模型解释呈现；知识引用用于说明一般训练原则；限制提示说明数据不足、能力范围或外部服务不可用。", "cap"), PageBreak(),
           p("六、今日训练建议：规则优先于语言解释", "h1"), image(derived["coach_today"], 16.3*cm, 18.0*cm), p("图 6  标注后的今日训练建议界面。① 为确定性规则结论；② 为计划与训练事实；③ 为受控 AI 解释；④ 为 Canonical Knowledge Reference。模型不能覆盖规则结论，也不能把知识库内容当成个人身体状态证明。", "cap"), PageBreak(),
           p("七、状态解释与知识依据", "h1"), image(ASSETS/"coach-agent"/"coach-rag-explain.png", 16.3*cm, 17.5*cm), p("图 7  解释当前 Runner State 时，界面展示规则结论、关键依据、限制与知识引用。训练知识只提供可追溯的一般原则；个人状态仍由训练事实、规则和数据完整度决定。", "cap"),
           p("八、部分事实并不等于全部不可分析", "h1"), image(ASSETS/"training-readiness"/"training-readiness2.png", 16.3*cm, 13.0*cm), p("图 8  训练准备情况详情。系统将数据不足、分析范围受限和当前能力限制分开表达：可判断域可继续给出受限结论；被阻塞域不生成确定断言。", "cap"), PageBreak(),
           p("九、Weekly Review：周训练事实与解释", "h1"), image(derived["weekly_review"], 16.3*cm, 16.5*cm), p("图 9  已标注的 Weekly Review。① 汇总本周完成情况；② 展示周训练事实与分析；③ 提出下一阶段的可审查建议。周复盘的作用是把训练计划和实际执行放在同一时间窗口中解释，而不是直接替代用户决策。", "cap"), PageBreak(),
           p("十、Proposal 与人机协同确认", "h1"), image(derived["weekly_proposal"], 16.3*cm, 16.5*cm), p("图 10  已标注的 Proposal 界面。① 将原安排与拟议安排并列；② 用户确认入口清晰可见。Proposal 是待确认方案，而非已经生效的正式计划；后端仍会检查所有权、版本、规则与事务条件。", "cap"),
           p("十一、Provider 降级时保留训练管理核心", "h1"), image(ASSETS/"coach-agent"/"coach-degraded-fallback.png", 16.3*cm, 12.5*cm), p("图 11  外部模型不可用时的安全降级。界面不会伪造模型回答，而是保留确定性规则建议、已有训练事实和限制提示。这使模型故障不会中断核心训练管理流程。", "cap"), PageBreak(),
           p("十二、产品闭环小结", "h1"), tbl(["步骤", "用户看到的内容", "系统保证"], [["训练计划", "周期、日历和每日训练安排。", "计划与实际执行分离。"], ["训练执行", "训练日志与授权设备同步结果。", "仅将成功归一化的数据进入事实层。"], ["状态与建议", "Runner State、准备情况、今日建议。", "先事实与规则，后解释。"], ["知识依据", "来源、章节和版本化引用。", "引用不替代个人事实。"], ["周复盘与方案", "本周分析、调整方案、确认入口。", "未确认方案不写入正式计划。"], ["异常降级", "模型或知识不可用提示。", "不泄露技术细节，不伪造结果。"]], [3.1*cm, 6.5*cm, 6.7*cm]), p("截图来源：GaitLogic 现有产品界面；Garmin 页面已生成脱敏裁剪副本。", "note")]
    return build("03_GaitLogic系统功能与运行截图.pdf", st)


def retrieval_safety() -> Path:
    st = cover("GaitLogic 检索与安全评测说明", "训练知识引用、事实边界与受控建议机制")
    st += [p("第一部分：为什么训练知识不能只依赖模型参数记忆", "h1"), p("通用模型能够生成自然语言，但不天然提供本项目训练知识的来源、版本与适用边界。GaitLogic 将训练知识组织为可检索 Corpus，并把最终公开引用还原为 Canonical Knowledge Reference。这样，用户可以看到训练原则的来源；同时，知识检索不会替代个人训练事实、Runner State 或确定性规则。"), tbl(["Corpus 项目", "已核验信息", "边界"], [["有效文档", "52 份", "包含项目原创训练原则与公开资料的结构化自写总结。"], ["可检索片段", "304 个", "片段保留文档、章节、来源与版本等 Metadata。"], ["来源类别", "5 类", "项目训练原则、丹尼尔斯训练法结构化总结、公开耐力训练指导、力量与伤病风险共识等。"], ["内容策略", "引用定位而非长文复制", "不向用户返回知识片段全文或内部索引标识。"]], [3.0*cm, 4.5*cm, 8.8*cm]),
           p("第二部分：检索流程与 Metadata Filter", "h1"), StepFlow(["Query", "Metadata Filter", "Dense", "BM25", "Fusion", "Reranker", "Canonical Reference"], height=3.2*cm), p("图 1  训练知识检索链路。Metadata Filter 按文档类型、来源、版本、语言和适用范围限制候选集合；Dense 与 BM25 分别从语义和关键词角度召回；Fusion 合并候选；Reranker 对候选排序；最终只将经过服务端还原的公开引用交给前端。", "cap"), PageBreak(),
           p("第三部分：Metadata 与 Chunk 的作用", "h1"), tbl(["字段类别", "示例作用", "安全价值"], [["来源与文档", "定位训练原则来自何种公开资料或项目原创文档。", "防止把无来源内容伪装为知识依据。"], ["章节与主题", "将阈值跑、恢复周、力量训练等主题定位到对应片段。", "减少跨主题的错误引用。"], ["版本与语言", "区分知识版本和适用语言。", "支持可追溯与可替换。"], ["适用范围", "限制候选适用于一般训练解释，而非个人医学判断。", "防止检索越界。"]], [3.1*cm, 6.8*cm, 6.4*cm]), p("这里使用的是 Metadata Filter，而不是独立的“Metadata Retrieval”策略：Metadata 主要负责在候选生成前施加可审查的筛选边界。", "note"),
           p("第四部分：真实检索案例的呈现方式", "h1"), tbl(["用户问题类型", "检索目标", "最终呈现"], [["阈值训练如何安排", "找到与阈值训练目的、强度控制或巡航间歇相关的公开原则。", "文档标题、章节、来源和受控短摘要。"], ["恢复周如何理解", "找到恢复周与负荷调整的原则。", "Canonical Reference，不把知识内容说成个人恢复结论。"], ["疼痛风险边界", "找到训练管理中的保守边界说明。", "提示需寻求专业医疗意见，不输出诊断。"]], [3.5*cm, 6.2*cm, 6.6*cm]), PageBreak(),
           p("第五部分：60 例公开检索集的演进与失败分析", "h1"), p("密集向量基线在固定公开 60 例检索集上通过 43/60，保留 17 个 RETRIEVAL_FAILURE。后续检索质量工作并未改写标签、查询、语料分段、Filter 或 top-k=4，而是先对失败作分类分析：BM25 恢复了其中 11 个 Dense 失败；6 个在两种策略下仍失败；BM25 还在 Dense 原先成功的案例中引入 2 个失败。"), tbl(["观察", "真实结果", "工程含义"], [["Dense 基线", "43/60 通过；17 个失败。", "作为可复现基准。"], ["BM25 对 Dense 失败的补充", "恢复 11/17；6 个仍失败。", "关键词证据与语义证据具有互补性。"], ["Metadata / Filter", "0 个确认的 filter violation。", "Filter 边界没有在该失败分析中失效。"], ["共享失败", "多文档覆盖、相关性歧义或候选排序问题。", "不能用临时查询改写或标签调整掩盖。"]], [3.2*cm, 4.5*cm, 8.6*cm]),
           p("第六部分：独立 Holdout v2 的检索观察", "h1"), p("另有一套独立公开虚构 holdout，包含 40 例，不能与上述 60 例数据集直接合并为单一提升率。其作用是观察不同检索策略在另一协议下的 Recall@4、MRR@4、nDCG@4、禁用文档率和延迟。策略选择由人工安全门禁决定，不通过“合成总分”自动选择。"), tbl(["策略", "Pass", "Recall@4", "MRR@4", "nDCG@4", "禁用文档率", "P50/P95"], [["Dense Exact", "33/40", "0.9369", "0.9144", "0.8908", "0.10", "560/1151 ms"], ["BM25", "29/40", "0.8694", "0.8784", "0.8533", "0.05", "11/12 ms"], ["Hybrid RRF", "32/40", "0.9189", "0.8716", "0.8599", "0.075", "124/137 ms"], ["Rerank", "33/40", "0.9324", "0.9324", "0.9166", "0.075", "568/666 ms"]], [2.6*cm, 1.7*cm, 2.0*cm, 1.8*cm, 1.8*cm, 2.3*cm, 3.0*cm]), PageBreak(),
           p("第七部分：剩余失败并未被隐藏", "h1"), tbl(["真实失败类别", "代表情况", "为什么不能直接“修高分”"], [["多文档语义/词法歧义", "一个问题需要多个相关文档，候选覆盖或排序不足。", "Reranker 无法召回根本没有进入候选集合的文档。"], ["硬相关性歧义", "训练主题之间概念相近，但目标章节不同。", "需要人工审查标签与语料覆盖，不能硬编码案例。"], ["禁用文档问题", "某些策略仍出现禁用文档。", "这是相关性/安全质量信号，不是 Metadata Filter 已经通过的证明。"], ["环境跳过", "Qdrant 策略在该 holdout 中记录为环境跳过。", "不能将未完成策略写成通过或默认最优。"]], [3.2*cm, 5.2*cm, 8.4*cm]), p("公开 60 例上的最终检索评测结论会在版本化报告中继续跟踪；本材料不以不同数据集、不同策略或不同协议混合制造单一“提升数字”。", "note"),
           p("第八部分：安全问题与用户可见表现", "h1"), tbl(["真实风险问题", "GaitLogic 的处理", "用户最终看到什么"], [["RPE 缺失", "按事实域区分：可判断域继续，主观疲劳域保留限制。", "受限结论与数据不足说明。"], ["RAG 检索不到", "不伪造来源；知识引用为空并加入友好限制。", "规则建议仍可用，说明未找到直接依据。"], ["模型 Provider 失败", "进入确定性 Fallback；不抛出原始错误。", "规则建议、训练事实与模型不可用提示。"], ["AI 想改正式计划", "只能生成 Proposal；需用户确认并再次校验。", "明确的待确认方案，不自动生效。"], ["调用方传入他人身份", "身份由服务端上下文注入，公开请求不接受 user_id。", "拒绝访问，不泄露对象存在性。"]], [3.3*cm, 7.2*cm, 6.3*cm]), PageBreak(),
           p("第九部分：固定协议/安全回归的含义", "h1"), tbl(["回归组", "结果", "主要验证内容"], [["Coach", "32/32", "公开意图、工具约束、决策一致性、降级与限制保留。"], ["RAG", "36/36", "知识工具、引用还原、决策不变性与来源幻觉边界。"], ["Weekly", "32/32", "周训练事实、规则一致性、回滚和 Proposal 写入安全。"], ["MCP", "45/45", "工具发现、身份隔离、只读与资源安全。"], ["Evidence Reflect", "10/10", "受控补证、证据状态和安全合同。"]], [3.0*cm, 2.3*cm, 11.5*cm]), p("以上是固定协议与安全回归结果，不是开放世界模型准确率“100%”。它们说明在明确边界的虚构测试契约中，系统没有出现预设的越权写入、来源幻觉或身份隔离问题。", "note"),
           p("第十部分：安全降级的真实界面证据", "h1"), image(ASSETS/"coach-agent"/"coach-degraded-fallback.png", 16.3*cm, 12.5*cm), p("图 2  模型解释不可用时，系统保留规则建议、训练事实和限制提示。外部服务异常不会被伪装成正常模型回答，也不会显示内部路径、凭据或原始异常。", "cap"), PageBreak(),
           p("第十一部分：评测结论与参考资料", "h1"), *bullets(["RAG 用于解释一般训练原则，不改变 TODAY 的确定性训练决策，也不绕开 Runner State、规则或 Validator。", "检索流程通过 Metadata Filter、候选生成、融合、重排序和 Canonical Reference 建立可追溯边界；每一步都需要单独验证。", "安全设计的关键不是“模型永不失败”，而是在数据不足、检索为空、Provider 失败和写入请求出现时，系统仍给出受控且可理解的结果。", "当前限制：Corpus 规模有限；不同检索策略在不同数据集的表现不能直接比较；外部服务的可用性仍可能影响解释。"]), p("参考资料", "h1"), *bullets(["GaitLogic 版本化 Corpus Manifest、Retrieval Failure Analysis、Retrieval Holdout v2 与固定安全回归记录。", "BM25、向量检索、Qdrant 与重排序相关公开技术文档。", "Daniels 训练理论与公开耐力训练资料的结构化自写知识总结；不复制大段原文。"]), PageBreak(),
           p("第十二部分：知识引用的生成与展示边界", "h1"), tbl(["阶段", "服务端控制内容", "不向调用方公开的内容"], [["候选检索", "按 Query 与 Metadata 过滤生成候选集合。", "内部向量、候选分数和完整片段正文。"], ["排序与选择", "Dense、BM25、融合与重排序产生候选排序。", "内部检索参数、运行目录与文件路径。"], ["引用还原", "将选择结果映射为 Canonical Reference。", "内部 Reference ID、索引标识与存储细节。"], ["前端展示", "来源、文档、章节、版本与受控短摘要。", "完整知识 Chunk、数据库对象和技术异常。"]], [3.0*cm, 6.9*cm, 6.5*cm]), p("这种“先检索、后还原、再公开”的结构是安全边界的一部分。它使用户可以理解引用来自哪里，却不能通过接口获取知识库内部对象、全量内容或服务配置。", "note"),
           p("第十三部分：从故障到可解释降级", "h1"), StepFlow(["训练事实可用", "知识检索异常", "不伪造引用", "保留规则结论", "展示限制", "用户继续查看"], height=3.1*cm), p("图 3  检索异常时的产品行为。RAG 是解释增强层：当它不可用时，系统会保留已有的训练事实和确定性规则结论，并明确说明“未找到直接依据”或“知识服务暂不可用”，而不是生成看似可信的来源。", "cap"), tbl(["故障类别", "安全处理", "验证重点"], [["Index 缺失或过期", "Readiness 检查失败，业务主体仍可启动。", "不返回内部目录、索引名或堆栈。"], ["Embedding Provider 失败", "不将失败包装为知识命中。", "不保存 Provider 原始响应。"], ["空检索", "Reference 为空并添加限制。", "不凭空补造文献来源。"], ["模型解释失败", "进入确定性 Fallback。", "TODAY 的规则结论保持不变。"]], [3.2*cm, 7.2*cm, 6.0*cm])]
    return build("04_GaitLogic检索与安全评测说明.pdf", st)


def validation_legacy() -> Path:
    st = cover("GaitLogic 用户内测与产品验证说明", "以真实产品流程、阶段性验证与问题闭环说明小范围试用")
    st += [p("一、材料说明与内测目的", "h1"), p("经项目目录、辅助材料目录与可访问下载目录的可核验文件检索，未发现可公开核验的问卷原始结果或统计数据。因此本材料不编造样本数、满意度、跑龄分布或使用意愿百分比，而是说明产品已经进行的阶段性功能验证、真实产品路径与持续收集反馈的设计。"), tbl(["验证目标", "关注问题", "不在本材料中声称的内容"], [["可理解性", "用户能否区分训练事实、规则建议与模型解释。", "未公开问卷的满意度比例。"], ["可解释性", "用户能否看到关键依据、知识引用与限制。", "医疗或伤病诊断有效性。"], ["安全性", "数据不足、模型失败、计划修改时边界是否清晰。", "自动修改正式训练计划。"], ["闭环性", "计划—执行—状态—周复盘—确认是否连贯。", "长期竞赛成绩提升承诺。"]], [3.0*cm, 6.5*cm, 7.3*cm]),
           p("二、小范围试用的产品路径", "h1"), StepFlow(["建立训练计划", "记录/同步训练", "查看状态", "使用 Coach", "周复盘", "确认方案"], height=3.2*cm), p("图 1  用于试用与验证的产品路径。每一步都有独立界面和边界：计划与实际分离，状态显示证据，Coach 先呈现规则，Proposal 需用户确认。", "cap"), PageBreak(),
           p("三、重点验证维度与产品证据", "h1"), Table([[image(ASSETS/"coach-agent"/"coach-overview.png", 7.9*cm, 9.5*cm), image(ASSETS/"runner-state"/"runner-state1.png", 7.9*cm, 9.5*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 2  Coach 与 Runner State。验证重点不是“模型回答是否更像人”，而是事实、规则、AI 解释和限制能否被用户清晰区分。", "cap"), tbl(["验证维度", "界面证据", "验证要点"], [["训练事实", "计划、日志、Runner State。", "计划不能被误当作实际完成。"], ["解释与引用", "Coach、知识依据、限制区。", "模型解释不覆盖规则结论。"], ["异常处理", "降级页、数据不足提示。", "不显示原始技术错误。"], ["计划变更", "Weekly Review、Proposal。", "方案需确认且不能自动写入。"]], [3.0*cm, 5.8*cm, 8.0*cm]), PageBreak(),
           p("四、阶段性产品验证案例", "h1"), Table([[image(ASSETS/"coach-agent"/"coach-rag-today.png", 7.9*cm, 8.8*cm), image(ASSETS/"coach-agent"/"coach-degraded-fallback.png", 7.9*cm, 8.8*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 3  今日建议与模型降级。左图验证“规则建议先于 AI 解释、关键依据可见”；右图验证“模型不可用时不伪造回答，核心规则结论仍保留”。", "cap"), tbl(["案例", "真实系统行为", "用户可理解的边界"], [["部分数据", "分开提示可判断域与受限域。", "不是所有字段缺失都会导致整体拒答。"], ["知识引用", "展示 Canonical Reference。", "知识解释不等于个人身体结论。"], ["模型不可用", "进入确定性 Fallback。", "显示可用事实与限制，而非技术堆栈。"], ["计划方案", "先生成 Proposal，再等待确认。", "未确认不会修改正式计划。"]], [3.0*cm, 6.7*cm, 7.1*cm]), PageBreak(),
           p("五、Weekly Review 与 Proposal 的闭环验证", "h1"), Table([[image(IMAGES/"weekly-review1.png", 7.9*cm, 10.5*cm), image(IMAGES/"weekly-review3.png", 7.9*cm, 10.5*cm)]], colWidths=[8.1*cm,8.1*cm]), p("图 4  周复盘与 Proposal。左图将本周计划、实际训练、负荷与状态纳入同一窗口；右图呈现调整前后对比与确认入口。该流程验证“分析能力”与“正式计划写入”之间存在明确的人机协同边界。", "cap"),
           p("六、当前已发现的问题与改进方向", "h1"), tbl(["已观察到的问题", "真实原因", "当前处理与后续方向"], [["部分数据时仍可能偏保守", "某些域缺失、冲突或 Proposal 写入安全要求会触发阻塞。", "已采用域级充分性判断；继续减少不必要的整体阻塞，但不降低写入安全。"], ["高级解释对普通跑者仍偏技术化", "Evidence、数据质量和训练术语具有工程复杂度。", "界面将规则建议、事实依据和限制分层呈现，并持续优化中文表达。"], ["录入完整度影响个性化", "RPE、睡眠、训练阶段、结构化分段等输入并非始终完整。", "明确区分数据不足、分析受限和当前能力限制，避免伪造结论。"], ["外部服务可能不可用", "模型、Embedding 或检索服务存在外部依赖。", "确定性规则和降级路径保留基础训练管理能力。"]], [4.2*cm, 5.5*cm, 7.1*cm]), PageBreak(),
           p("七、后续反馈收集与隐私原则", "h1"), p("后续小范围试用将围绕“是否有用、是否个性化、事实是否可信、解释是否清晰、是否愿意持续使用”收集匿名反馈；同时记录使用场景与问题分类。该反馈设计不要求收集不必要的身份信息、医疗信息、精确轨迹或访问凭据。任何用户训练数据均不作为公开比赛材料的一部分。"), tbl(["反馈维度", "建议记录", "隐私边界"], [["使用场景", "今日建议、状态解释、周复盘或计划方案。", "不记录完整对话和训练正文。"], ["理解与采纳", "解释是否清晰、风险提示是否合理、是否愿意采纳。", "不关联公开身份。"], ["问题分类", "数据不足、引用、界面、Provider 降级、计划确认。", "不公开个人训练记录。"], ["授权状态", "是否允许用于匿名产品改进。", "可撤回，不公开原始信息。"]], [3.0*cm, 6.5*cm, 7.3*cm]), p("结论：当前材料证明的是产品已具备可运行的试用与验证路径，并如实保留了仍需持续改进的问题；它不以未经核验的问卷数字或用户规模作为项目能力证明。", "note")]
    return build("05_GaitLogic用户内测与产品验证说明.pdf", st)


def validation_feedback() -> Path:
    """Build the v2 user-study report from the supplied anonymised N=50 data."""
    st = cover("GaitLogic 用户内测与产品验证说明", "用户体验与阶段性反馈（N=50 模拟占位汇总，提交前需核验）")
    st += [
        p("一、用户体验与阶段性反馈", "h1"),
        p("本章按照提供的 N=50 汇总数字呈现 AI 建议、事实解释、周复盘与计划调整的体验观察。当前数字为模拟占位汇总，用于校验比赛材料的统计结构与图表版式；正式提交前必须由匿名原始反馈、问卷导出或合规访谈编码核验并替换。无论使用何种正式数据，结果都只能用于产品改进与比赛展示，不用于证明医疗有效性或运动成绩提升。", "body"),
        tbl(["验证方向", "关注问题", "边界"], [["事实可信", "建议是否体现个人训练情况、是否能解释数据不足。", "不作医疗诊断或成绩提升承诺。"], ["决策支持", "周复盘与计划调整是否提供增量信息。", "不替代教练或自动修改正式计划。"], ["体验改进", "功能使用、困惑点和持续使用意愿。", "仅反映本轮匿名样本的阶段性反馈。"]], [3.0*cm, 7.0*cm, 6.8*cm]),
        p("二、测试用户构成", "h1"),
        tbl(["跑龄", "人数", "占比"], [["不足 1 年", "9", "18%"], ["1-3 年", "18", "36%"], ["3-5 年", "14", "28%"], ["5 年以上", "9", "18%"]], [7.0*cm, 4.5*cm, 4.5*cm]), Spacer(1, 0.18*cm),
        tbl(["周跑量", "人数", "占比"], [["<20 km", "7", "14%"], ["20-40 km", "18", "36%"], ["40-60 km", "15", "30%"], [">60 km", "10", "20%"]], [7.0*cm, 4.5*cm, 4.5*cm]),
        p("样本覆盖从初跑者到有多年训练经验的跑者，并包含不同周跑量区间；更适合观察功能理解、训练事实呈现与决策支持的感知反馈，而非进行竞技表现推断。", "note"), PageBreak(),
        p("三、实际体验功能", "h1"), p("测试者实际体验了 AI 对话、训练计划、状态评估、周复盘、负荷恢复、设备数据与计划调整等主要训练管理环节。", "body0"),
        HorizontalBarChart("图 1  各功能实际体验比例", ["AI Coach", "训练计划 / 日历", "Runner State", "智能周复盘", "训练负荷与恢复", "Garmin / 设备数据", "Plan Proposal / 计划调整"], [94, 90, 80, 74, 70, 58, 62], 100, "%", height=9.2*cm),
        tbl(["功能", "体验人数", "占比"], [["AI Coach", "47", "94%"], ["训练计划 / 日历", "45", "90%"], ["Runner State", "40", "80%"], ["智能周复盘", "37", "74%"], ["训练负荷与恢复", "35", "70%"], ["Garmin / 设备数据", "29", "58%"], ["Plan Proposal / 计划调整", "31", "62%"]], [8.0*cm, 4.0*cm, 4.0*cm]), PageBreak(),
        p("四、核心体验评价", "h1"), p("采用 5 分 Likert 量表。图中横轴从 0 到 5 分完整呈现，不截断为 4-5 分，以避免夸大不同评价维度之间的视觉差异。", "body0"),
        tbl(["评价维度", "均值 ± 标准差"], [["建议对当前训练是否有用", "4.34 ± 0.57"], ["建议是否体现个人训练情况", "4.16 ± 0.66"], ["对训练事实描述的可信度", "4.42 ± 0.52"], ["结论与限制说明是否清晰", "4.28 ± 0.61"], ["知识依据是否有助于理解", "4.18 ± 0.64"], ["数据不足时的谨慎程度", "4.46 ± 0.50"], ["智能周复盘的实际价值", "4.27 ± 0.63"], ["计划调整方案合理性", "4.08 ± 0.71"], ["整体使用体验", "4.25 ± 0.58"]], [11.2*cm, 4.8*cm]),
        p("阶段性观察", "h2"),
        tbl(["观察", "对应结果", "产品含义"], [["事实与边界", "可信度 4.42；谨慎程度 4.46。", "用户重视建议是否基于真实训练事实，以及限制是否表达清楚。"], ["周复盘价值", "智能周复盘 4.27。", "统一复盘计划、执行与状态信息具有感知价值。"], ["计划调整", "合理性 4.08。", "仍需在个性化偏好和调整幅度上继续优化。"]], [3.2*cm, 4.2*cm, 8.6*cm]), PageBreak(),
        p("四、核心体验评价（续）", "h1"),
        HorizontalBarChart("图 2  核心体验评价（5 分制）", ["当前训练建议有用性", "个人训练匹配度", "训练事实可信度", "结论与限制清晰度", "知识依据理解帮助", "数据不足时的谨慎程度", "智能周复盘价值", "计划调整合理性", "整体使用体验"], [4.34, 4.16, 4.42, 4.28, 4.18, 4.46, 4.27, 4.08, 4.25], 5, " / 5", height=16.8*cm),
        p("受试者对训练事实可信度、数据不足时的谨慎程度和当前训练建议的有用性给出较高评价。", "note"), PageBreak(),
        p("五、持续使用意愿与 Decision Support", "h1"),
        tbl(["持续使用意愿", "人数", "占比"], [["愿意继续使用", "42", "84%"], ["暂不确定", "6", "12%"], ["暂不愿继续使用", "2", "4%"]], [8.0*cm, 4.0*cm, 4.0*cm]), Spacer(1, 0.25*cm),
        HorizontalBarChart("图 3  持续使用意愿", ["愿意继续使用", "暂不确定", "暂不愿继续使用"], [84, 12, 4], 100, "%", height=5.2*cm),
        p("Decision Support", "h2"), p("该指标关注系统是否为训练判断提供实际增量信息，而不是是否证明系统能提升运动成绩。", "body0"),
        tbl(["用户感知的决策支持", "人数", "占比"], [["提供此前忽略的信息", "16", "32%"], ["帮助确认原有判断", "18", "36%"], ["有帮助地改变原计划 / 判断", "9", "18%"], ["没有明显额外帮助", "5", "10%"], ["造成一定困惑", "2", "4%"]], [8.0*cm, 4.0*cm, 4.0*cm]), Spacer(1, 0.16*cm),
        HorizontalBarChart("图 4  用户感知的决策支持", ["提供此前忽略的信息", "帮助确认原有判断", "有帮助地改变原计划 / 判断", "没有明显额外帮助", "造成一定困惑"], [32, 36, 18, 10, 4], 100, "%", height=5.1*cm),
        p("Positive Decision Support = 前三项合计 43/50（86%）。该指标反映用户是否认为系统在训练决策中提供实际增量信息，不证明系统能够提升运动成绩。", "note"), PageBreak(),
        p("六、反馈主题与产品问题", "h1"),
        tbl(["反馈主题", "涉及人数", "产品启示"], [["能把分散训练数据放到一起分析", "21", "持续强化计划、日志、状态与设备数据的统一事实视图。"], ["周复盘比单纯跑量统计更有价值", "17", "保持周计划、实际执行与状态信息的联合复盘。"], ["数据不足时主动说明限制更可信", "15", "保留数据质量和限制说明，避免把缺失扩展为确定结论。"], ["训练知识引用有助于理解建议原因", "13", "继续提供可追溯、简洁的知识依据。"], ["部分回答仍偏保守", "11", "在安全边界内减少不必要的全局阻塞。"], ["部分专业术语理解成本较高", "8", "优化中文表达与术语分层说明。"], ["计划调整希望有更多个性化选择", "7", "加强偏好、调整幅度与反馈后二次生成。"], ["数据同步与录入仍有操作成本", "6", "持续降低设备同步与手工记录门槛。"]], [7.1*cm, 2.5*cm, 6.4*cm]),
        p("七、用户反馈结果解读", "h1"),
        p("阶段性结果显示，用户更关注 AI 建议是否建立在真实训练事实之上，而不仅仅是生成内容是否丰富。训练事实可信度为 4.42/5，数据不足时的谨慎程度为 4.46/5，当前训练建议的有用性为 4.34/5。这说明事实边界、限制说明和可理解的建议，是当前产品信任感的重要来源。", "body"),
        p("智能周复盘获得 4.27/5，表明将一周训练计划、实际执行与状态信息统一复盘具有较好的感知价值。Plan Proposal 的合理性为 4.08/5，相对其他指标略低；结合反馈主题，后续将重点增强个体训练偏好、调整幅度以及用户反馈后的二次生成能力。", "body"),
        p("下一阶段优先改进", "h2"), tbl(["优先级", "拟解决的问题", "对应反馈"], [["1", "在安全约束下减少不必要的保守阻塞。", "部分回答仍偏保守。"], ["2", "提供更易理解的术语解释与分层表达。", "部分专业术语理解成本较高。"], ["3", "支持更多偏好、调整幅度和反馈后二次生成。", "计划调整希望有更多个性化选择。"]], [1.5*cm, 8.3*cm, 6.2*cm]), PageBreak(),
        p("八、与系统评测结果的呼应", "h1"),
        p("用户反馈中“部分回答仍偏保守”的问题，与 AI 消融实验中完整系统仍存在 41.03% False Global Block 的现象方向一致，形成相互印证的问题线索。两者来自不同实验和不同评价对象：用户体验反馈并不验证该 41.03% 数值，也不能替代受控消融评测。", "body"),
        tbl(["观察来源", "发现", "可采取的改进"], [["用户阶段性反馈", "部分回答偏保守，计划调整仍期待更多个性化。", "完善偏好输入、幅度控制与二次生成交互。"], ["AI 消融评测", "完整系统仍存在 False Global Block。", "继续优化域级充分性判断，降低不必要的全局阻塞。"]], [3.5*cm, 5.8*cm, 6.7*cm]),
        p("九、结论与隐私边界", "h1"),
        p("本轮内测表明，GaitLogic 在事实可信度、数据不足场景下的谨慎表达、当前建议有用性与周复盘感知价值方面获得积极的阶段性反馈。产品仍需持续改善计划调整的个性化、专业术语可理解性及数据同步与录入体验。", "body"),
        tbl(["隐私原则", "执行方式"], [["匿名反馈", "反馈匿名收集，仅用于产品改进与比赛展示。"], ["最小必要", "不收集不必要身份信息；不公开个人训练记录。"], ["敏感信息保护", "不公开精确 GPS、医疗详情或访问凭据。"], ["聚合展示", "仅展示聚合统计，不展示可识别个人的原始数据。"]], [4.0*cm, 12.0*cm]),
        p("阶段性结果的适用边界", "h2"), tbl(["可以支持的表述", "不应扩展为"], [["本轮样本对事实可信、谨慎表达与周复盘价值给出了阶段性正向反馈。", "系统已被证明提升运动成绩、医学效果或可替代专业人员。"], ["Decision Support 反映用户感知的增量信息。", "系统能够保证每项训练决策均正确。"]], [8.0*cm, 8.0*cm]),
        p("GaitLogic 是训练管理与决策支持工具，不替代专业教练、医生或康复师。", "note")
    ]
    return build("05_GaitLogic用户内测与产品验证说明.pdf", st)


def validation_feedback_legacy() -> Path:
    """Build the superseded simulated feedback placeholder."""
    st = cover("GaitLogic 用户内测与产品验证说明", "用户体验与阶段性反馈（模拟占位汇总，提交前需核验）")
    st += [p("一、内测背景、目的与数据说明", "h1"), p("本报告新增“用户体验与阶段性反馈”章节，用于呈现测试者对训练事实、规则建议、AI 解释、周复盘与计划调整的体验观察。以下 N=50 的样本构成、使用情况和评价统计为用户提供的模拟占位汇总，目的是预先校验比赛材料的统计结构和可视化呈现；在正式提交前，必须以可追溯的匿名原始反馈、问卷导出或访谈编码完成核验与替换。"), tbl(["项目", "本版口径", "使用边界"], [["样本规模", "N = 50（模拟占位）。", "不得视为已核验真实招募数量。"], ["评价方法", "5 分 Likert 量表，报告均值 ± 标准差。", "须保留题项、量表说明与匿名原始记录。"], ["反馈用途", "识别产品可理解性、决策支持和改进方向。", "不能推导训练成绩或伤病改善。"], ["展示原则", "仅展示聚合统计与主题归纳。", "不公开身份、训练记录、GPS 或访问凭据。"]], [3.0*cm, 5.7*cm, 8.1*cm]),
           p("二、测试用户构成", "h1"), tbl(["维度", "分组", "人数", "占比"], [["跑龄", "不足 1 年", "9", "18%"], ["", "1–3 年", "18", "36%"], ["", "3–5 年", "14", "28%"], ["", "5 年以上", "9", "18%"], ["周跑量", "＜20 km", "7", "14%"], ["", "20–40 km", "18", "36%"], ["", "40–60 km", "15", "30%"], ["", "＞60 km", "10", "20%"]], [2.6*cm, 5.0*cm, 3.0*cm, 3.0*cm]), HorizontalBarChart("图 1  跑龄构成（横轴：人数，0–50）", ["不足 1 年", "1–3 年", "3–5 年", "5 年以上"], [9,18,14,9], 50, "人", height=5.0*cm), p("样本构成用于观察不同训练经验和周跑量下的体验差异。由于本版数据尚属模拟占位，报告不进一步宣称组间差异、显著性或人群代表性。", "note"), PageBreak(),
           p("三、实际体验功能", "h1"), HorizontalBarChart("图 2  各功能的体验人数（横轴：人数，0–50）", ["AI Coach", "训练计划/日历", "Runner State", "智能周复盘", "训练负荷与恢复", "Garmin/设备数据", "Plan Proposal"], [47,45,40,37,35,29,31], 50, "人", height=11.2*cm), tbl(["功能", "体验人数", "比例", "说明"], [["AI Coach", "47", "94%", "面向今日建议、状态解释和一般训练问题。"], ["训练计划/日历", "45", "90%", "提供计划安排与实际训练的时间视图。"], ["Runner State", "40", "80%", "展示状态、关键依据与数据限制。"], ["智能周复盘", "37", "74%", "将计划、执行和状态纳入周级解释。"], ["训练负荷与恢复", "35", "70%", "呈现近期训练量与恢复相关线索。"], ["Garmin/设备数据", "29", "58%", "在授权范围内补充训练事实。"], ["Plan Proposal", "31", "62%", "展示待确认的计划调整方案。"]], [3.3*cm, 2.3*cm, 2.0*cm, 8.2*cm]), PageBreak(),
           p("四、核心体验评价", "h1"), HorizontalBarChart("图 3  核心体验均值（横轴：1–5 分，完整量程）", ["当前训练建议有用性", "体现个人训练情况", "训练事实可信度", "结论与限制清晰度", "知识依据帮助理解", "数据不足时的谨慎度", "周复盘实际价值", "计划调整合理性", "整体使用体验"], [4.34,4.16,4.42,4.28,4.18,4.46,4.27,4.08,4.25], 5, "", height=16.8*cm), p("图表横轴固定从 0 到 5，不通过截断坐标轴放大细小差异；每一项均显示完整量程，避免视觉夸大。", "cap"), PageBreak(),
           p("五、核心体验评价的统计表与解读", "h1"), tbl(["评价维度", "均值 ± 标准差", "阶段性解读"], [["建议对当前训练是否有用", "4.34 ± 0.57", "总体有用性较高，但不等同于训练效果提升。"], ["建议是否体现个人训练情况", "4.16 ± 0.66", "个体化感受仍有优化空间。"], ["训练事实描述可信度", "4.42 ± 0.52", "测试者更认可来自训练事实的描述。"], ["结论与限制说明清晰", "4.28 ± 0.61", "规则结论与限制分层呈现具有价值。"], ["知识依据有助理解", "4.18 ± 0.64", "引用能帮助解释原因，但仍需降低理解成本。"], ["数据不足时的谨慎程度", "4.46 ± 0.50", "保守表达被视为重要的安全体验。"], ["智能周复盘实际价值", "4.27 ± 0.63", "周计划、执行与状态统一复盘具有感知价值。"], ["计划调整方案合理性", "4.08 ± 0.71", "相对较低，反映需要更多个性化选择。"], ["整体使用体验", "4.25 ± 0.58", "用于整体体验的阶段性观察。"]], [5.5*cm, 3.3*cm, 7.0*cm]), p("在该模拟汇总中，训练事实可信度（4.42）、数据不足时的谨慎度（4.46）与当前训练建议有用性（4.34）相对较高。这一组合更接近“用户重视建议是否建立在真实事实和明确边界上”，而非单纯追求内容丰富或语言流畅。智能周复盘为 4.27/5，表明将周计划、实际执行和状态统一呈现具有感知价值；Plan Proposal 为 4.08/5，提示下一轮应把训练偏好、调整幅度与用户反馈后的二次生成做得更细。", "note"), tbl(["优先改进方向", "对应体验线索", "拟提升的产品能力"], [["个体训练偏好", "“体现个人训练情况”与 Proposal 相对较低。", "补充目标、可接受训练量与偏好约束。"], ["调整幅度说明", "用户希望了解方案为何这样变化。", "展示调整前后差异、原因与安全边界。"], ["二次生成", "一次 Proposal 难覆盖所有使用偏好。", "在不自动写计划的前提下支持受控反馈。"]], [3.7*cm, 5.7*cm, 6.4*cm]), PageBreak(),
           p("六、持续使用意愿与 Decision Support", "h1"), Table([[HorizontalBarChart("图 4  持续使用意愿（0–50 人）", ["愿意继续使用", "暂不确定", "暂不愿继续使用"], [42,6,2], 50, "人", width=8.0*cm, height=7.0*cm), HorizontalBarChart("图 5  决策支持类型（0–50 人）", ["提供此前忽略信息", "帮助确认原有判断", "有帮助地改变判断", "没有额外帮助", "造成一定困惑"], [16,18,9,5,2], 50, "人", width=8.0*cm, height=7.0*cm)]], colWidths=[8.1*cm,8.1*cm]), tbl(["持续使用意愿", "人数", "比例"], [["愿意继续使用", "42", "84%"], ["暂不确定", "6", "12%"], ["暂不愿继续使用", "2", "4%"]], [6.0*cm, 3.0*cm, 3.0*cm]), tbl(["Decision Support 类型", "人数", "比例"], [["提供此前忽略的信息", "16", "32%"], ["帮助确认原有判断", "18", "36%"], ["有帮助地改变原计划/判断", "9", "18%"], ["没有明显额外帮助", "5", "10%"], ["造成一定困惑", "2", "4%"]], [6.0*cm, 3.0*cm, 3.0*cm]), p("Positive Decision Support = 前三项合计 43/50 = 86%。该指标仅反映测试者是否感到系统在训练决策中提供了增量信息，不证明系统能够提升运动成绩、预测伤病或替代专业教练。持续使用意愿与决策支持类型属于不同问题：前者反映继续接触产品的态度，后者反映本次训练判断是否获得新增信息，两者不应简单相互替代。", "note"), PageBreak(),
           p("七、反馈主题归纳与产品问题", "h1"), tbl(["反馈主题", "涉及人数", "产品启示"], [["能把分散训练数据放到一起分析", "21", "继续保持计划、日志、状态与设备事实的统一视图。"], ["周复盘比单纯跑量统计更有价值", "17", "强化“计划—执行—状态”的周级解释。"], ["数据不足时主动说明限制更可信", "15", "保留域级充分性与限制提示，不伪造确定结论。"], ["训练知识引用有助于理解建议原因", "13", "持续提供来源与章节，降低引用理解成本。"], ["部分回答仍偏保守", "11", "减少不必要的整体阻塞，但不放宽写入安全。"], ["部分专业术语理解成本较高", "8", "优化中文解释与术语分层。"], ["计划调整希望有更多个性化选择", "7", "补充偏好、调整幅度与二次生成能力。"], ["数据同步与录入仍有操作成本", "6", "改善同步反馈与必要字段的录入体验。"]], [6.2*cm, 2.6*cm, 7.0*cm]),
           p("八、结果解读、系统评测呼应与隐私边界", "h1"), p("模拟反馈中“部分回答仍偏保守”的主题，与 AI 消融实验里完整系统仍有 41.03% 错误整体阻塞这一现象方向一致，形成后续产品优化的问题线索；两者属于不同实验，不能把用户反馈解释为对该 41.03% 指标的验证。计划调整合理性为 4.08/5，也与“需要更多训练偏好、调整幅度和反馈后二次生成”的主题一致。"), tbl(["从反馈得到的线索", "可与系统评测形成的关系", "不能作出的推论"], [["部分回答偏保守", "与错误整体阻塞问题方向一致。", "不能由用户反馈反推或验证 41.03%。"], ["事实可信与谨慎度较高", "与事实、规则和限制优先的产品设计相符。", "不能推导训练成绩提升。"], ["Proposal 评价相对较低", "支持继续优化个性化和确认前解释。", "不等于允许系统自动修改计划。"]], [4.0*cm, 6.0*cm, 5.8*cm]), p("隐私原则：反馈采用匿名聚合方式；不公开个人训练记录、精确 GPS、医疗详情、身份信息或访问凭据；聚合统计仅用于产品改进与比赛展示。正式提交前，应以真实匿名数据替换本章模拟占位数据，并保留合规的数据来源、统计过程和受试者告知记录。", "note")]
    return build("05_GaitLogic用户内测与产品验证说明.pdf", st)


def package(files: list[Path]) -> Path:
    target = OUT / "做梦想达一级_GaitLogic跑者训练智能体_其他.zip"
    with ZipFile(target, "w", ZIP_DEFLATED) as zf:
        for pdf in files:
            zf.write(pdf, pdf.name)
    return target


def main() -> None:
    global S
    fonts(); S = make_styles(); derived = annotate_assets()
    files = [technical(), ablation(), screenshots(derived), retrieval_safety(), validation_feedback()]
    archive = package(files)
    print("Generated:")
    for item in files + [archive]: print(item)


if __name__ == "__main__":
    main()

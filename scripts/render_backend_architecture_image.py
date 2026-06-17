from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "images" / "backend-learning-architecture.png"
W, H = 1920, 1180


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/NotoSansSC-VF.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/Dengb.ttf" if bold else "C:/Windows/Fonts/Deng.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


img = Image.new("RGB", (W, H), "#f5f7fb")
d = ImageDraw.Draw(img)

f_title = load_font(42, True)
f_sub = load_font(24)
f_group = load_font(25, True)
f_box = load_font(23, True)
f_small = load_font(18)

palette = {
    "entry": ("#e8f4ff", "#4f9ed9", "#0f3554"),
    "deploy": ("#edf2ff", "#6c8bd7", "#202b55"),
    "app": ("#f2f5f9", "#8796a8", "#172033"),
    "domain": ("#ebf9f0", "#51a96e", "#16351f"),
    "core": ("#fff5df", "#d89b2b", "#3b2b08"),
    "external": ("#f7ebfb", "#ad78ca", "#321240"),
}


def text_width(text: str, font: ImageFont.ImageFont) -> int:
    box = d.textbbox((0, 0), text, font=font)
    return box[2] - box[0]


def round_rect(box, fill, outline, width=3, radius=24):
    d.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def group_box(x: int, y: int, w: int, h: int, title: str, key: str):
    fill, outline, text = palette[key]
    round_rect((x, y, x + w, y + h), "#ffffff", outline, 3, 26)
    d.rounded_rectangle((x, y, x + w, y + 48), radius=24, fill=fill, outline=outline, width=0)
    d.rectangle((x, y + 24, x + w, y + 48), fill=fill)
    d.text((x + 22, y + 10), title, fill=text, font=f_group)


def box(x: int, y: int, w: int, h: int, title: str, subtitle: str, key: str):
    fill, outline, text = palette[key]
    round_rect((x, y, x + w, y + h), fill, outline, 2, 18)
    lines = title.split("\n")
    ty = y + 18
    for line in lines:
        d.text((x + (w - text_width(line, f_box)) / 2, ty), line, fill=text, font=f_box)
        ty += 30
    if subtitle:
        sy = y + h - 34
        d.text((x + (w - text_width(subtitle, f_small)) / 2, sy), subtitle, fill="#667085", font=f_small)


d.text((70, 46), "GaitLogic Planner 后端整体架构", fill="#172033", font=f_title)
d.text((72, 100), "从前端请求到 FastAPI、业务服务、ORM、MySQL 与 AI / Excel 依赖的完整链路", fill="#667085", font=f_sub)

gap = 32
col_w = 330
x1 = 70
x2 = x1 + col_w + gap
x3 = x2 + col_w + gap
x4 = x3 + col_w + gap
x5 = x4 + col_w + gap
y0 = 170

group_box(x1, y0, col_w, 840, "入口层", "entry")
group_box(x2, y0, col_w, 840, "部署与网关", "deploy")
group_box(x3, y0, col_w, 840, "FastAPI 应用层", "app")
group_box(x4, y0, col_w, 840, "业务层", "domain")
group_box(x5, y0, col_w, 840, "基础设施 / 外部依赖", "core")

boxes = {}


def add(name, x, y, w, h, title, subtitle, key):
    boxes[name] = (x, y, w, h)
    box(x, y, w, h, title, subtitle, key)


bw, bh = 264, 86
bx = lambda x: x + 33
add("web", bx(x1), 250, bw, bh, "Vue 前端", "浏览器页面", "entry")
add("docs", bx(x1), 380, bw, bh, "Swagger 文档", "/api/docs", "entry")
add("tests", bx(x1), 510, bw, bh, "pytest 测试", "TestClient", "entry")

add("nginx", bx(x2), 270, bw, bh, "Nginx", "反向代理 / 静态资源", "deploy")
add("runtime", bx(x2), 430, bw, bh, "后端进程", "Gunicorn / Uvicorn", "deploy")

add("main", bx(x3), 230, bw, bh, "server/main.py", "创建 app / 注册模块", "app")
add("routes", bx(x3), 360, bw, bh, "API Routes", "server/api/routes/*", "app")
add("deps", bx(x3), 490, bw, bh, "Depends", "Session / 当前用户", "app")
add("schemas", bx(x3), 620, bw, bh, "Pydantic Schemas", "请求与响应结构", "app")

add("services", bx(x4), 215, bw, bh, "Services", "业务逻辑 / 事务", "domain")
add("calendar", bx(x4), 340, bw, bh, "日历 / Dashboard", "统计与汇总", "domain")
add("excel", bx(x4), 465, bw, bh, "Excel 导入", "模板 / 校验 / 入库", "domain")
add("ai", bx(x4), 590, bw, bh, "AI 课表草稿", "限额 / 缓存 / 校验", "domain")
add("pace", bx(x4), 715, bw, bh, "配速 / VDOT", "训练配速区间", "domain")

add("auth", bx(x5), 215, bw, bh, "JWT 鉴权", "识别 current_user", "core")
add("session", bx(x5), 340, bw, bh, "SQLAlchemy Session", "get_db / engine", "core")
add("models", bx(x5), 465, bw, bh, "ORM Models", "models.py", "core")
add("mysql", bx(x5), 590, bw, bh, "MySQL 8.0", "gaitlogic_planner", "external")
add("ext", bx(x5), 715, bw, bh, "外部服务", "DeepSeek / openpyxl", "external")


def center_right(name):
    x, y, w, h = boxes[name]
    return x + w, y + h / 2


def center_left(name):
    x, y, w, h = boxes[name]
    return x, y + h / 2


def center_bottom(name):
    x, y, w, h = boxes[name]
    return x + w / 2, y + h


def center_top(name):
    x, y, w, h = boxes[name]
    return x + w / 2, y


def arrow(a, b, color="#667085", width=4):
    ax, ay = a
    bx_, by = b
    midx = (ax + bx_) / 2
    d.line((ax, ay, midx, ay, midx, by, bx_, by), fill=color, width=width, joint="curve")
    d.polygon([(bx_, by), (bx_ - 12, by - 7), (bx_ - 12, by + 7)], fill=color)


def varrow(a, b, color="#667085", width=4):
    ax, ay = a
    bx_, by = b
    d.line((ax, ay, bx_, by), fill=color, width=width)
    d.polygon([(bx_, by), (bx_ - 7, by - 12), (bx_ + 7, by - 12)], fill=color)


arrow(center_right("web"), center_left("nginx"))
arrow(center_right("docs"), center_left("nginx"))
arrow(center_right("tests"), center_left("main"))
varrow(center_bottom("nginx"), center_top("runtime"))
arrow(center_right("runtime"), center_left("main"))
varrow(center_bottom("main"), center_top("routes"))
varrow(center_bottom("routes"), center_top("deps"))
varrow(center_bottom("deps"), center_top("schemas"))
arrow(center_right("routes"), center_left("services"))
arrow(center_right("services"), center_left("auth"))
arrow(center_right("services"), center_left("session"))
arrow(center_right("services"), center_left("models"))
arrow(center_right("models"), center_left("mysql"))
arrow(center_right("excel"), center_left("ext"))
arrow(center_right("ai"), center_left("ext"))

round_rect((70, 1040, W - 70, 1108), "#ffffff", "#d7dee8", 2, 18)
note = "主线：请求进入 FastAPI → 路由接参数 → 依赖注入当前用户和数据库 Session → Service 执行业务 → ORM 访问 MySQL → Schema 返回前端。"
d.text((96, 1060), note, fill="#344054", font=f_sub)

OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, quality=95)
print(OUT)

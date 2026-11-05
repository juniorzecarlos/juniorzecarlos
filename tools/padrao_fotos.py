"""Padrão de foto Warez 3DWorld: troca o fundo por parede com a logo e dá um leve ajuste de luz.
O produto não é alterado (só brilho/contraste leve).

Uso: python3 tools/padrao_fotos.py catalogo/marca/logo-warez3dworld.png ORIG1 SAIDA1 [ORIG2 SAIDA2 ...]
Requer: pip install "rembg[cpu]" scipy pillow numpy
"""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from scipy import ndimage as nd
from rembg import remove, new_session

W, H = 1080, 1350
LOGO = sys.argv[1]
sess = new_session("isnet-general-use")

def logo_rgba(path):
    lg = Image.open(path).convert("RGBA")
    if lg.getchannel("A").getextrema()[0] < 250:
        return lg.crop(lg.getbbox())
    a = np.asarray(lg).astype(float)
    # fundo branco do logo -> transparente
    white = (a[..., :3].min(-1) > 235)
    lab, _ = nd.label(white); border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]])) - {0}
    m = np.isin(lab, list(border))
    alpha = np.where(m, 0, 255).astype(np.uint8)
    lg.putalpha(Image.fromarray(alpha).filter(ImageFilter.GaussianBlur(1)))
    return lg.crop(lg.getbbox())

def process(src, dst, logo):
    im = Image.open(src).convert("RGB")
    rgb = np.asarray(im).astype(float)
    # 1) máscara do produto: IA + regra de cor (fundo = claro e sem saturação)
    ai = np.asarray(remove(im, session=sess, only_mask=True)).astype(float) / 255
    mx, mn = rgb.max(-1), rgb.min(-1)
    sat = (mx - mn) / (mx + 1)
    dark = nd.binary_closing(mx < 60, iterations=10)  # preto (suporte/botas), fecha a colmeia
    lab, n = nd.label(dark)
    if n:
        big_c = lab == (1 + np.argmax(nd.sum(dark, lab, range(1, n + 1))))
        xs_ = np.where(big_c.any(0))[0]; span = xs_.max() - xs_.min() + 1
        for y in np.where(big_c.any(1))[0]:          # tampo da bancada: preenche linha a linha
            row = np.where(big_c[y])[0]
            if row.size > 0.45 * span:
                dark[y, row.min():row.max() + 1] = True
    fg = dark | (sat > 0.35)                          # ou cor forte
    fg = nd.binary_opening(fg, iterations=2)
    lab, n = nd.label(fg); sizes = nd.sum(fg, lab, range(1, n + 1))
    fg = np.isin(lab, 1 + np.where(sizes > 0.002 * fg.size)[0])
    fg = fg | (ai > 0.5)
    fg = nd.binary_closing(fg, structure=np.ones((3, 3)), iterations=14)  # rosto/barba branca colado na parede
    holes = nd.binary_fill_holes(fg) & ~fg          # só tapa buracos pequenos (barba branca)
    hl, hn = nd.label(holes); hs = nd.sum(holes, hl, range(1, hn + 1))
    fg = fg | np.isin(hl, 1 + np.where(hs < 0.004 * fg.size)[0])
    rule = np.asarray(Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
    alpha = np.maximum(ai, rule)
    alpha = np.where(alpha > 0.97, 1, np.where(alpha < 0.12, 0, alpha))
    alpha = np.minimum(alpha, nd.grey_erosion(alpha, size=3)) ** 1.4   # tira o halo branco
    # 2) leve correção de luz só no produto
    prod = Image.fromarray(rgb.astype(np.uint8))
    prod = ImageEnhance.Brightness(prod).enhance(1.06)
    prod = ImageEnhance.Contrast(prod).enhance(1.08)
    prod = ImageEnhance.Color(prod).enhance(1.05)
    prod = np.asarray(prod).astype(float)
    # 3) sombra: luminância do fundo original relativa ao fundo "limpo"
    lum = rgb.mean(-1)
    m = (alpha < 0.05).astype(float)
    m = nd.binary_erosion(m, iterations=4).astype(float)
    g = lambda x, r: nd.gaussian_filter(x, r)
    big = g(lum * m, 40) / np.maximum(g(m, 40), 1e-3)          # fundo "limpo" estimado
    shade = np.where(m > 0, lum / np.maximum(big, 1), 1.0)
    shade = np.clip(g(shade, 2), 0.5, 1.0)
    shade = 1 - np.clip((1 - shade) - 0.08, 0, 1) / 0.92   # ignora variação leve da parede
    # 4) recorte e enquadramento 4:5
    ys, xs = np.where(alpha > 0.3)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h, w = rgb.shape[:2]
    pad = int(0.08 * max(y1 - y0, x1 - x0))
    y0, y1 = max(0, y0 - pad), min(h, y1 + pad); x0, x1 = max(0, x0 - pad), min(w, x1 + pad)
    area_h = int(H * 0.68)  # 32% de cima é da logo
    s = min(W * 0.94 / (x1 - x0), area_h / (y1 - y0))
    def fit(arr, mode):
        return np.asarray(Image.fromarray(arr[y0:y1, x0:x1]).resize((int((x1 - x0) * s), int((y1 - y0) * s)), mode))
    P = fit(prod.astype(np.uint8), Image.LANCZOS).astype(float)
    A = fit((alpha * 255).astype(np.uint8), Image.LANCZOS).astype(float)[..., None] / 255
    S = fit((shade * 255).astype(np.uint8), Image.LANCZOS).astype(float)[..., None] / 255
    fy = np.clip(np.minimum(np.arange(S.shape[0]), S.shape[0] - 1 - np.arange(S.shape[0])) / 60, 0, 1)[:, None]
    fx = np.clip(np.minimum(np.arange(S.shape[1]), S.shape[1] - 1 - np.arange(S.shape[1])) / 60, 0, 1)[None, :]
    S = 1 - (1 - S) * (fy * fx)[..., None]              # sombra some suave nas bordas
    # 5) cenário: parede quente em degradê + bancada
    yy = np.linspace(0, 1, H)[:, None, None]
    xx = np.linspace(-1, 1, W)[None, :, None]
    top, bot = np.array([255, 246, 228]), np.array([238, 222, 196])
    scene = top * (1 - yy) + bot * yy
    scene = scene * (1 - 0.10 * xx ** 2)  # vinheta suave
    scene = np.broadcast_to(scene, (H, W, 3)).copy()
    ph, pw = P.shape[:2]
    oy, ox = H - ph - int(H * 0.03), (W - pw) // 2
    # bancada: faixa inferior mais escura a partir de ~base do produto
    desk = int(oy + ph * 0.80)
    scene[desk:] *= 0.93
    scene[desk:desk + 3] *= 0.9
    # logo na parede
    lw = int(W * 0.46); lg = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    if lg.height > H * 0.30:
        lh = int(H * 0.30); lg = logo.resize((int(logo.width * lh / logo.height), lh), Image.LANCZOS)
    base = Image.fromarray(scene.clip(0, 255).astype(np.uint8)).convert("RGBA")
    sh = Image.new("RGBA", lg.size, (0, 0, 0, 0)); sh.putalpha(lg.getchannel("A").point(lambda v: v * 0.25))
    lx, ly = (W - lg.width) // 2, int(H * 0.025)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)), (lx + 6, ly + 10))
    base.alpha_composite(lg, (lx, ly))
    scene = np.asarray(base.convert("RGB")).astype(float)
    reg = scene[oy:oy + ph, ox:ox + pw]
    reg = reg * (S * (1 - A) + A)            # transfere sombras originais
    reg = reg * (1 - A) + P * A               # produto por cima
    scene[oy:oy + ph, ox:ox + pw] = reg
    Image.fromarray(scene.clip(0, 255).astype(np.uint8)).save(dst, quality=92)

logo = logo_rgba(LOGO)
for src, dst in zip(sys.argv[2::2], sys.argv[3::2]):
    process(src, dst, logo); print("ok", dst)

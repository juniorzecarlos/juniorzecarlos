"""Padrão de foto Warez 3DWorld: troca o fundo por parede com a logo e dá um leve ajuste de luz.
O produto não é alterado (só brilho/contraste leve).

Uso: python3 tools/padrao_fotos.py [--estilo=madeira|estudio|marca] catalogo/marca/logo-warez3dworld.png ORIG1 SAIDA1 [ORIG2 SAIDA2 ...]
Requer: pip install "rembg[cpu]" scipy pillow numpy
"""
import sys, numpy as np
from PIL import Image, ImageFilter, ImageEnhance
from scipy import ndimage as nd
from rembg import remove, new_session

W, H = 1080, 1350
sess = new_session("isnet-general-use")   # borda fina
sess2 = new_session("u2net")              # pega o miolo branco (barba/rosto) que o isnet às vezes perde

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

def process(src, dst, logo, estilo):
    im = Image.open(src).convert("RGB")
    rgb = np.asarray(im).astype(float)
    # 1) máscara do produto: IA + regra de cor (fundo = claro e sem saturação)
    ai = np.asarray(remove(im, session=sess, only_mask=True)).astype(float) / 255
    u2 = np.asarray(remove(im, session=sess2, only_mask=True)) > 200
    u2 = nd.binary_erosion(u2, iterations=8)          # só o miolo, a borda fica com o isnet
    ai = np.maximum(ai, (u2 & (ai > 0.12)).astype(float))   # só reforça onde o isnet já viu algo
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
    fg = nd.binary_closing(fg, structure=np.ones((3, 3)), iterations=22)  # rosto/barba branca colado na parede
    holes = nd.binary_fill_holes(fg) & ~fg          # só tapa buracos pequenos (barba branca)
    hl, hn = nd.label(holes); hs = nd.sum(holes, hl, range(1, hn + 1))
    fg = fg | np.isin(hl, 1 + np.where(hs < 0.004 * fg.size)[0])
    rule = np.asarray(Image.fromarray((fg * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2))) / 255
    alpha = np.maximum(ai, rule)
    alpha = np.where(alpha > 0.97, 1, np.where(alpha < 0.12, 0, alpha))
    alpha = np.minimum(alpha, nd.grey_erosion(alpha, size=3)) ** 1.4   # tira o halo branco
    # 2) leve correção de luz só no produto
    prod = Image.fromarray(rgb.astype(np.uint8))
    prod = np.asarray(prod).astype(float)
    prod = 255 * (prod / 255) ** 0.82                 # "abre" a foto: clareia meios-tons sem estourar o branco
    prod = Image.fromarray(prod.clip(0, 255).astype(np.uint8))
    prod = ImageEnhance.Contrast(prod).enhance(1.06)
    prod = ImageEnhance.Color(prod).enhance(1.06)
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
    # 4) recorte e enquadramento 4:5 (foto aberta: produto ocupa ~metade do quadro)
    h, w = rgb.shape[:2]
    ys, xs = np.where(alpha > 0.3)
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    toca_esq, toca_dir = x0 <= 2, x1 >= w - 3
    pad = int(0.04 * max(y1 - y0, x1 - x0))
    y0, y1 = max(0, y0 - pad), min(h, y1 + pad); x0, x1 = max(0, x0 - pad), min(w, x1 + pad)
    s = min(W * 0.80 / (x1 - x0), H * 0.50 / (y1 - y0))
    def fit(arr):
        return np.asarray(Image.fromarray(arr[y0:y1, x0:x1]).resize((int((x1 - x0) * s), int((y1 - y0) * s)), Image.LANCZOS)).astype(float)
    P = fit(prod.astype(np.uint8))
    A = fit((alpha * 255).astype(np.uint8))[..., None] / 255
    S = fit((shade * 255).astype(np.uint8))[..., None] / 255
    ph, pw = P.shape[:2]
    ramp = lambda n, k: np.clip(np.arange(n) / k, 0, 1)
    fy = np.minimum(ramp(ph, 50), ramp(ph, 50)[::-1])[:, None]
    fx = np.minimum(ramp(pw, 50), ramp(pw, 50)[::-1])[None, :]
    S = 1 - (1 - S) * (fy * fx)[..., None]
    # se o suporte saía cortado na foto original, esmaece a ponta em vez de mostrar o corte seco
    fade = np.ones(pw)
    if toca_esq: fade = np.minimum(fade, ramp(pw, pw * 0.12))
    if toca_dir: fade = np.minimum(fade, ramp(pw, pw * 0.12)[::-1])
    escuro = (P.max(-1, keepdims=True) < 110)          # só o suporte preto esmaece, nunca o produto colorido
    A = np.where(escuro, A * fade[None, :, None], A)
    oy, ox = int(H * 0.90) - ph, (W - pw) // 2
    desk = int(oy + ph * 0.80)
    scene = cenario(estilo, desk, (ox + pw / 2, oy + ph * 0.45))
    # logo na parede
    lw = int(W * 0.40); lg = logo.resize((lw, int(logo.height * lw / logo.width)), Image.LANCZOS)
    lh_max = max(120, oy - int(H * 0.06))
    if lg.height > lh_max:
        lg = logo.resize((int(logo.width * lh_max / logo.height), lh_max), Image.LANCZOS)
    base = Image.fromarray(scene.clip(0, 255).astype(np.uint8)).convert("RGBA")
    sh = Image.new("RGBA", lg.size, (0, 0, 0, 0)); sh.putalpha(lg.getchannel("A").point(lambda v: v * 0.30))
    lx, ly = (W - lg.width) // 2, int(H * 0.035)
    base.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (lx + 6, ly + 12))
    base.alpha_composite(lg, (lx, ly))
    scene = np.asarray(base.convert("RGB")).astype(float)
    reg = scene[oy:oy + ph, ox:ox + pw]
    reg = reg * (S * (1 - A) + A)            # sombras originais
    reg = reg * (1 - A) + P * A              # produto por cima
    scene[oy:oy + ph, ox:ox + pw] = reg
    Image.fromarray(scene.clip(0, 255).astype(np.uint8)).save(dst, quality=93)


def madeira(h, w, c_claro, c_escuro, seed=3):
    rng = np.random.default_rng(seed)
    y = np.arange(h)[:, None]; x = np.arange(w)[None, :]
    ruido = nd.gaussian_filter(rng.standard_normal((h, w)), (2, 60)) * 40
    veio = 0.5 + 0.5 * np.sin((y + ruido) * 0.35 + np.sin(x / 140) * 2)
    veio = veio ** 3 * 0.6 + nd.gaussian_filter(rng.standard_normal((h, w)), (1, 25)) * 1.5
    t = np.clip(veio, 0, 1)[..., None]
    return np.array(c_claro) * (1 - t) + np.array(c_escuro) * t


def cenario(estilo, desk, foco):
    yy = np.linspace(0, 1, H)[:, None, None]
    X, Y = np.meshgrid(np.arange(W), np.arange(H))
    r = np.sqrt(((X - foco[0]) / W) ** 2 + ((Y - foco[1]) / H * 1.25) ** 2)[..., None]
    if estilo == "estudio":      # parede grafite com luz de spot atrás do produto
        parede = np.array([46, 52, 64]) + np.array([95, 98, 105]) * np.exp(-(r / 0.38) ** 2)
        mesa_a, mesa_b = np.array([70, 72, 78]), np.array([36, 37, 42])
    elif estilo == "marca":      # amarelo da marca com luz central
        parede = np.array([236, 168, 30]) + np.array([19, 70, 140]) * np.exp(-(r / 0.45) ** 2)
        mesa_a, mesa_b = np.array([250, 244, 235]), np.array([222, 212, 198])
    else:                        # "madeira": parede off-white + bancada de madeira
        parede = np.array([246, 244, 240]) - np.array([28, 30, 34]) * yy - np.array([18, 18, 18]) * np.clip(r - 0.3, 0, 1)
        mesa_a = mesa_b = None
    scene = np.broadcast_to(parede, (H, W, 3)).copy()
    mh = H - desk
    if mesa_a is None:
        tampo = madeira(mh, W, (214, 168, 120), (160, 110, 70))
    else:
        t = np.linspace(0, 1, mh)[:, None, None]
        tampo = np.broadcast_to(mesa_a * (1 - t) + mesa_b * t, (mh, W, 3)).copy()
    tampo *= np.linspace(0.92, 1.04, mh)[:, None, None]
    scene[desk:] = tampo
    scene[desk:desk + 3] *= 1.08                                   # filete de luz na quina
    scene[max(0, desk - 25):desk] *= np.linspace(1, 0.9, min(25, desk))[:, None, None]  # sombrinha na parede
    return scene


ESTILOS = ("madeira", "estudio", "marca")
if __name__ == "__main__":
    args = sys.argv[1:]
    estilo = "madeira"
    if args and args[0].startswith("--estilo="):
        estilo = args.pop(0).split("=", 1)[1]
        assert estilo in ESTILOS, f"estilos: {ESTILOS}"
    logo = logo_rgba(args[0])
    for src, dst in zip(args[1::2], args[2::2]):
        process(src, dst, logo, estilo); print("ok", dst)

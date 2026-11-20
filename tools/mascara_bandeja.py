"""Gera máscara de bandeja oval ("pista de corrida") vista de frente/cima.
Uso: python3 tools/mascara_bandeja.py FOTO SAIDA.png x_esq x_dir y_tras y_frente_topo altura_borda raio_x
A máscara (branco = produto) é usada com: padrao_fotos.py --extra=SAIDA.png
"""
import sys, numpy as np
from PIL import Image, ImageFilter

foto, saida = sys.argv[1], sys.argv[2]
xe, xd, yt, yf, borda, rx = map(float, sys.argv[3:9])
w, h = Image.open(foto).size
Y, X = np.mgrid[0:h, 0:w].astype(float)
cy, ry = (yt + yf) / 2, (yf - yt) / 2

def estadio(dy):
    yy = Y - cy - dy
    dentro = (X >= xe + rx) & (X <= xd - rx) & (np.abs(yy) <= ry)
    for cx in (xe + rx, xd - rx):
        dentro |= ((X - cx) / rx) ** 2 + (yy / ry) ** 2 <= 1
    return dentro

m = np.zeros((h, w), bool)
for dy in np.arange(0, borda + 1, 2):          # topo da bandeja "extrudado" para baixo = borda frisada
    m |= estadio(dy)
Image.fromarray((m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)).save(saida)
print("ok", saida)

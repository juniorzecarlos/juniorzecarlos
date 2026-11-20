# Catálogo Warez 3DWorld

Fotos dos produtos para o catálogo.

```
catalogo/
  marca/                     logo usada no fundo
  produtos/<produto>/
    original/                foto como veio do celular (nunca editar)
    editada/                 foto no padrão vitrine (alternativas/ = outros cenários)
```

## Padrão das fotos
- Formato 1080x1350 (4:5 — serve pra Instagram e catálogo)
- Foto "aberta": produto ocupa ~metade do quadro, com respiro em volta, e meios-tons clareados
- Logo no topo da parede + bancada embaixo
- **Logo sempre a original** (`catalogo/marca/logo-warez3dworld.png`), nunca redesenhada
- Cenários (`--estilo=`):
  - `vitrine` (**padrão**): parede cinza com 3 spots de luz quente vindo de cima + bancada de mármore com reflexo do produto
  - `madeira`: parede off-white + bancada de madeira
  - `estudio`: parede grafite com spot de luz atrás + bancada escura
  - `marca`: parede amarela (cor da logo) + bancada creme
- Produto recortado do original **sem alteração**, só leve ajuste de brilho/contraste
- Sombras originais do produto preservadas

## Gerar novas
```bash
pip install "rembg[cpu]" scipy pillow numpy   # usa os modelos isnet + u2net
python3 tools/padrao_fotos.py --estilo=vitrine catalogo/marca/logo-warez3dworld.png \
  catalogo/produtos/X/original/foto.jpg catalogo/produtos/X/editada/foto.jpg
```

## Produto branco em fundo branco (IA não enxerga)
Quando parte do produto some no recorte (ex.: bandeja branca), gere uma máscara manual e passe com `--extra`:
```bash
# bandeja oval: x_esq x_dir y_tras y_frente_topo altura_borda raio_x (em pixels da foto original)
python3 tools/mascara_bandeja.py FOTO.jpg FOTO.mascara.png 22 1082 1100 1319 105 125
python3 tools/padrao_fotos.py --extra=FOTO.mascara.png catalogo/marca/logo-warez3dworld.png FOTO.jpg SAIDA.jpg
```
Qualquer PNG preto/branco do tamanho da foto serve (branco = produto) — dá pra pintar no celular também.

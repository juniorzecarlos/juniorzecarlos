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

# Catálogo Warez 3DWorld

Fotos dos produtos para o catálogo.

```
catalogo/
  marca/                     logo usada no fundo
  produtos/<produto>/
    original/                foto como veio do celular (nunca editar)
    editada/                 foto no padrão (fundo com logo + luz corrigida)
```

## Padrão das fotos
- Formato 1080x1350 (4:5 — serve pra Instagram e catálogo)
- Fundo: parede bege clara em degradê + logo no topo + leve "bancada" embaixo
- Produto recortado do original **sem alteração**, só leve ajuste de brilho/contraste
- Sombras originais do produto preservadas

## Gerar novas
```bash
pip install "rembg[cpu]" scipy pillow numpy
python3 tools/padrao_fotos.py catalogo/marca/logo-warez3dworld.png \
  catalogo/produtos/X/original/foto.jpg catalogo/produtos/X/editada/foto.jpg
```

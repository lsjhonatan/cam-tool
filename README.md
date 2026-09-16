# cam-tool

Ferramenta para medição automatizada de dimensões de gotas líquidas
em imagens e vídeos de laboratório.

Baseado conceitualmente em ContactAngleMeasurement de Mike Phillips
(https://github.com/MikePhillips123/ContactAngleMeasurement),
reescrito do zero com arquitetura própria em Python 3.

Licenciado sob GPLv3.

## Descrição

O cam-tool analisa vídeos de gotas depositadas sobre superfícies
sólidas e calcula, para cada frame selecionado:

- Largura da gota (diâmetro da base)
- Altura da gota
- Raio da esfera que contém a calota (R)
- Volume da calota
- Área de contato com a superfície
- Ângulo de contato (fórmula da calota esférica)

O modelo físico assumido é a aproximação de calota esférica
(sessile drop), adequada para gotas pequenas onde a gravidade é
desprezível.

## Recursos

- Segmentação automática da gota por limiarização de Otsu
- Detecção de contorno via OpenCV
- Ajuste robusto de linha de base com RANSAC
- Medição de largura, altura, raio, volume e área
- Cálculo do ângulo de contato por fórmula de calota esférica
- Calibração de escala (nanômetros por pixel)
- Interface gráfica com Dear PyGui
- Preview sob demanda da imagem analisada
- Exportação de resultados em CSV e XLSX
- Geração de slideshow em GIF ou MP4
- Configurações persistentes em Settings.txt

## Requisitos

- Python 3.10 ou superior
- Ubuntu 22.04 ou superior (testado no 26.04)
- Bibliotecas do sistema:
  - python3-venv
  - python3-full
  - python3-tk
  - libmediainfo0v5
- Bibliotecas Python (instaladas via pip):
  - dearpygui
  - opencv-python
  - numpy
  - pillow
  - pymediainfo
  - pandas
  - openpyxl

## Instalação

Clone o repositório:

```bash
git clone https://github.com/lsjhonatan/cam-tool.git
cd cam-tool
```

Execute o script de instalação:

```bash
./dependencias.sh
```

O script irá:

1. Instalar as dependências do sistema via apt
2. Criar o ambiente virtual em .venv
3. Instalar as dependências Python via pip
4. Adicionar aliases ao ~/.bashrc

Após a instalação, recarregue o shell:

```bash
source ~/.bashrc
```

## Uso

Ative o ambiente virtual e execute:

```bash
cam-tool
```

Ou diretamente:

```bash
cd ~/cam-tool
source .venv/bin/activate
python3 -m cam_tool
```

### Fluxo de trabalho

1. Selecione o arquivo de vídeo pelo botão "Selecionar vídeo"
2. Defina a escala em nanômetros por pixel (calibração da câmera)
3. Ajuste a região de interesse (ROI) nos campos x1 e x2
4. Clique em "Atualizar Preview" para visualizar o frame analisado
5. Ajuste os thresholds de análise se necessário
6. Configure o número de imagens, intervalo e formato de saída
7. Clique em "Compilar Slideshow" para processar todos os frames

### Saídas geradas

Os resultados são salvos em `~/cam-tool/Output/<nome_do_video>/`:

- `Images/` — imagens anotadas de cada frame (PNG)
- `<nome_do_video>.gif` ou `<nome_do_video>.mp4` — slideshow
- `<nome_do_video>_Medidas_[timestamp].xlsx` — planilha com as medidas

## Estrutura do projeto

```
cam-tool/
├── README.md
├── LICENSE
├── requirements.txt
├── dependencias.sh
├── Settings.txt
├── cam_tool/
│   ├── __init__.py
│   ├── __main__.py
│   ├── config.py
│   ├── log.py
│   ├── image.py
│   ├── video.py
│   ├── segmentation.py
│   ├── contour.py
│   ├── baseline.py
│   ├── measurements.py
│   ├── overlay.py
│   ├── pipeline.py
│   ├── export.py
│   ├── slideshow.py
│   └── gui/
│       ├── __init__.py
│       ├── app.py
│       ├── settings_tab.py
│       ├── logging_tab.py
│       ├── preview.py
│       └── widgets.py
├── tests/
└── examples/
```

## Arquitetura

O projeto é organizado em módulos com responsabilidades bem definidas.

### Módulos de infraestrutura

- **config.py**: gerenciamento de parâmetros persistentes
- **log.py**: logging unificado com suporte a callbacks (GUI)

### Módulos de entrada

- **image.py**: leitura e escrita de imagens
- **video.py**: leitura de vídeos e extração de frames

### Módulos de processamento

- **segmentation.py**: segmentação da gota por threshold
- **contour.py**: extração do maior contorno
- **baseline.py**: ajuste da linha de base com RANSAC
- **measurements.py**: cálculo das medidas (largura, altura, raio,
  volume, área, ângulo)

### Módulos de saída

- **overlay.py**: desenho dos elementos visuais na imagem
- **export.py**: exportação para CSV e XLSX
- **slideshow.py**: montagem de GIF e MP4

### Orquestração

- **pipeline.py**: classe DropletAnalyzer que orquestra o pipeline
  completo de análise

### Interface

- **gui/**: interface gráfica com Dear PyGui

## Metodologia

O pipeline de análise segue as etapas:

1. **Aquisição**: o frame é carregado e a correção de rotação é
   aplicada com base nos metadados do vídeo.

2. **Segmentação**: a imagem é convertida para escala de cinza,
   filtrada com desfoque gaussiano, invertida e binarizada pelo
   método de Otsu. Operações morfológicas de abertura e fechamento
   removem ruído e preenchem buracos. A região de interesse é
   aplicada como máscara.

3. **Extração do contorno**: o maior contorno é extraído com
   cv2.findContours e filtrado pelos limites da região de
   interesse.

4. **Ajuste da linha de base**: os N% mais baixos do contorno são
   selecionados e uma reta é ajustada com RANSAC (Random Sample
   Consensus), que é robusto a outliers.

5. **Medição**:
   - Largura: distância horizontal entre os dois pontos de contato
     (interseção contorno-baseline)
   - Altura: distância vertical entre o topo da gota e a baseline
   - Raio: R = (a² + h²) / (2h), onde a = largura/2 e h = altura
   - Volume: V = π h² (3R - h) / 3
   - Área: A = π a²
   - Ângulo: θ = 2 · atan(h / a)

6. **Renderização**: sobreposição dos elementos visuais (contorno,
   baseline, linhas de dimensão, rótulos de medidas).

7. **Exportação**: geração das imagens anotadas, slideshow e
   planilha de resultados.

## Calibração

A conversão de pixels para nanômetros é feita por um fator
fornecido pelo usuário. O valor deve ser obtido por calibração
da câmera com um objeto de referência de dimensão conhecida.

O campo "Escala (nm/px)" na interface define o fator. Por exemplo,
se 1 pixel equivale a 500 nanômetros, o valor deve ser 500.

## Licença

Este projeto é distribuído sob a GNU General Public License v3.0.
Veja o arquivo LICENSE para o texto completo.

## Créditos

Baseado conceitualmente em:

- **ContactAngleMeasurement** de Mike Phillips
  https://github.com/MikePhillips123/ContactAngleMeasurement

O cam-tool é uma reescrita independente, com arquitetura própria,
implementação do zero e modelo físico diferente (calota esférica
em vez de ajuste de elipse).
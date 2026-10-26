# Sistema de Detecção Dinâmica de Cones — Guia Completo

## 📋 Visão Geral

O sistema de detecção dinâmica de cones substitui a necessidade de calibração manual de linhas estáticas. Agora o sistema:

✅ **Detecta automaticamente os cones em tempo real**  
✅ **Encontra as bases dos cones (onde tocam o chão)**  
✅ **Cria uma linha dinâmica entre o cone mais à esquerda e mais à direita**  
✅ **Rastreia a linha mesmo com movimentos de câmera**  
✅ **Adapta-se a diferentes posições e ângulos de câmera**

---

## 🔧 Ativação

### 1. Arquivo `config.py`

No início do arquivo, encontre esta seção:

```python
# ==============================================================================
# Dinamik Koni Tespit Sistemi — Kamera Hareketine Dayanıklı Çizgiler
# ==============================================================================
ENABLE_CONE_DETECTION: bool = True      # Ativa a detecção dinâmica
```

**Para ATIVAR:**

```python
ENABLE_CONE_DETECTION = True
```

**Para DESATIVAR (voltar ao modo manual):**

```python
ENABLE_CONE_DETECTION = False
```

---

## ⚙️ Personalizações

### Cores dos Cones

Se seus cones não forem **laranja padrão**, ajuste os limites HSV em `config.py`:

```python
# Laranja padrão
CONE_HSV_LOWER = (0, 80, 80)        # Matiz 0-15 (laranja)
CONE_HSV_UPPER = (15, 255, 255)

# Laranja mais avermelhado
CONE_HSV_LOWER = (0, 100, 100)
CONE_HSV_UPPER = (10, 255, 255)

# Amarelo (para cones amarelos)
CONE_HSV_LOWER = (15, 50, 50)
CONE_HSV_UPPER = (35, 255, 255)

# Vermelho puro
CONE_HSV_LOWER = (170, 80, 80)
CONE_HSV_UPPER = (180, 255, 255)
```

### Tamanho e Forma dos Cones

```python
CONE_MIN_AREA_PX = 200              # Mínimo de pixels para detectar um cone
CONE_MAX_AREA_PX = 50000            # Máximo para bloquear falsos positivos
CONE_MIN_CIRCULARITY = 0.4          # Quanto mais circular, maior o valor (0-1)
```

**Guia:**

- **Diminuir `MIN_AREA`**: detecta cones pequenos (mais sensível)
- **Aumentar `MAX_AREA`**: detecta cones maiores (menos falsos positivos)
- **Aumentar `CIRCULARITY`**: apenas formas bem circulares

### Suavização de Movimento

```python
CONE_LINE_SMOOTHING_ALPHA = 0.7     # 0 = muito suave, 1 = sem suavização
```

**Se a linha treme:**
→ Aumentar para `0.8` ou `0.9`

**Se a linha tarda em atualizar:**
→ Diminuir para `0.5` ou `0.6`

### Debug/Visualização

```python
CONE_DEBUG_DRAW = True              # Desenha cones na imagem
```

Quando ativado, você verá:

- 🟦 **Círculos azuis**: centros dos cones detectados
- 🔴 **Círculos vermelhos**: bases dos cones (onde tocam o chão)
- 📏 **Linhas ciano**: conexão do centro à base

---

## 🚀 Como Usar

### Opção 1: Uso Automático (Recomendado)

1. Ative em `config.py`:

   ```python
   ENABLE_CONE_DETECTION = True
   ```

2. Execute normalmente:

   ```bash
   python dual_main.py --video seu_video.mp4
   ```

3. O sistema detectará os cones automaticamente em cada frame!

### Opção 2: Debug — Ver os Cones Detectados

1. Ative debug em `config.py`:

   ```python
   CONE_DEBUG_DRAW = True
   ```

2. Execute e veja os cones circulados na tela

3. Se os cones não aparecerem, ajuste cores conforme seção anterior

---

## 🔍 Troubleshooting

### Problema: Não detecta nenhum cone

**Solução 1:** Verificar cor

```python
CONE_HSV_LOWER = (0, 50, 50)        # Menos restritivo
CONE_HSV_UPPER = (20, 255, 255)
```

**Solução 2:** Aumentar sensibilidade

```python
CONE_MIN_AREA_PX = 100              # Reduz limite mínimo
```

**Solução 3:** Ativar debug

```python
CONE_DEBUG_DRAW = True
```

Veja se algo é detectado (mesmo se errado, ajustaremos a cor)

---

### Problema: Detecta muitos falsos positivos

**Solução 1:** Aumentar circularity

```python
CONE_MIN_CIRCULARITY = 0.6          # Mais exigente com forma
```

**Solução 2:** Reduzir máximo

```python
CONE_MAX_AREA_PX = 30000            # Bloqueia coisas grandes
```

**Solução 3:** Restringir cor

```python
CONE_HSV_LOWER = (5, 100, 100)      # Apenas laranja puro
CONE_HSV_UPPER = (12, 255, 255)
```

---

### Problema: Linha fica tremendo/oscilando

**Solução:** Aumentar suavização

```python
CONE_LINE_SMOOTHING_ALPHA = 0.85    # Mais suave
```

---

### Problema: Linha demora para atualizar depois de movimento de câmera

**Solução:** Reduzir suavização

```python
CONE_LINE_SMOOTHING_ALPHA = 0.5     # Mais responsiva
```

---

## 📊 Como Funciona Internamente

```
Frame de vídeo
       ↓
   [HSV Thresholding] ← cor do cone (Laranja/Vermelho)
       ↓
   [Morphology] ← limpeza de ruído
       ↓
   [Find Contours] ← detecta bordas
       ↓
   [Filter by Size & Shape] ← valida cones
       ↓
   [Ordena por X] ← esquerda para direita
       ↓
   [Encontra Base] ← ponto mais baixo de cada cone
       ↓
   [Cria Linha] ← entre cone extremo esquerdo e direito
       ↓
   [Temporal Smoothing] ← suaviza oscilações
       ↓
   Linha dinâmica pronta para detecção de cruzamento!
```

---

## 🔧 Arquivos Adicionados

1. **`cone_detector.py`**
   - Módulo de detecção HSV de cones
   - Classes: `Cone`, `ConeLine`, `ConeDetector`, `DynamicLineTracker`

2. **`cone_line_adapter.py`**
   - Integração com sistema PerspectiveLine existente
   - Classe: `ConeLineAdapter`

3. **`CONE_DETECTION_USAGE.txt`**
   - Instruções rápidas

4. **`CONE_DETECTION_README.md`** (este arquivo)
   - Documentação completa

---

## 💡 Dicas Profissionais

### 1. Calibrar Cores com OpenCV

Para encontrar os valores HSV exatos dos seus cones:

```python
import cv2
import numpy as np

cap = cv2.VideoCapture('seu_video.mp4')
ret, frame = cap.read()
hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

# Clique para ver HSV
def mouse_callback(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        h, s, v = hsv[y, x]
        print(f"HSV: ({h}, {s}, {v})")

cv2.namedWindow('Frame')
cv2.setMouseCallback('Frame', mouse_callback)
cv2.imshow('Frame', frame)
cv2.waitKey(0)
```

Clique sobre um cone para ver seu HSV exato.

### 2. Testar em Tempo Real

```bash
# Com debug ativado para ver cones
python dual_main.py --video test.mp4 --no-display
```

### 3. Armazenar Configuração

Após ajustar e testar, salve em `config.py`:

```python
# Config testada para cones laranja do formato X
CONE_HSV_LOWER = (0, 80, 80)
CONE_HSV_UPPER = (15, 255, 255)
CONE_MIN_AREA_PX = 250
CONE_MAX_AREA_PX = 40000
CONE_MIN_CIRCULARITY = 0.5
CONE_LINE_SMOOTHING_ALPHA = 0.75
```

---

## 📝 Notas

- O sistema detecta **até 2 cones por frame** (extremo esquerdo e direito)
- Se houver 3+ cones, usa apenas os dois extremos
- Se não encontrar cones, volta à linha anterior (fallback)
- A suavização temporal impede oscilações da câmera

---

## 🎬 Exemplo de Uso Completo

```bash
# 1. Editar config.py
ENABLE_CONE_DETECTION = True
CONE_DEBUG_DRAW = True

# 2. Executar
python dual_main.py --video video.mp4

# 3. Ver cones detectados na tela (azul/vermelho)

# 4. Se ok, desativar debug para vídeo final
CONE_DEBUG_DRAW = False

# 5. Executar novamente para gerar saída
python dual_main.py --video video.mp4 --no-display
```

---

**Perguntas?** Verifique se `cone_detector.py` e `cone_line_adapter.py` estão na mesma pasta que `dual_main.py`.

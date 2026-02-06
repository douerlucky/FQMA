import numpy as np
import matplotlib.pyplot as plt

# Data
models = ["DeepSeek-v3", "Qwen-1.5+", "GPT-4o-mini", "Gemini 2.0"]
shots = ["0-shot", "2-shot", "5-shot"]

FEX = np.array([
    [55.7, 70.2, 90.1],   # DeepSeek
    [26.0, 32.8, 65.6],   # Qwen
    [5.3, 19.8, 33.6],    # GPT
    [0.0, 10.7, 18.3],    # Gemini
])

SEX = np.array([
    [77.5, 88.0, 91.1],
    [56.2, 53.4, 78.6],
    [39.2, 35.4, 48.3],
    [46.3, 54.2, 58.5],
])

x = np.arange(len(models))
width = 0.22

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

# --- FEX plot ---
for i in range(3):
    ax1.bar(x + (i-1)*width, FEX[:, i], width, label=shots[i])

ax1.set_ylabel("FEX (%)")
ax1.set_title("FEX Comparison under Different Shots")
ax1.legend()
ax1.grid(axis="y", linestyle="--", alpha=0.6)

# --- SEX plot ---
for i in range(3):
    ax2.bar(x + (i-1)*width, SEX[:, i], width, label=shots[i])

ax2.set_ylabel("SEX (%)")
ax2.set_title("SEX Comparison under Different Shots")
ax2.set_xticks(x)
ax2.set_xticklabels(models, rotation=15)
ax2.grid(axis="y", linestyle="--", alpha=0.6)

plt.tight_layout()
plt.show()

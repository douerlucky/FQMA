import matplotlib.pyplot as plt
import numpy as np

# -------------------------
# Data
# -------------------------
llms = ['Deepseek-v3', 'Qwen-1.5-plus', 'GPT-4o-mini', 'Gemini-2.0-Flash']

fex_0 = [55.7, 26.0, 5.3, 0.0]
fex_2 = [70.2, 32.8, 19.8, 10.7]
fex_5 = [90.1, 65.6, 33.6, 18.3]

sex_0 = [77.5, 56.2, 39.2, 46.3]
sex_2 = [88.0, 53.4, 35.4, 54.2]
sex_5 = [91.1, 78.6, 48.3, 58.5]

x = np.arange(len(llms))
width = 0.25

# -------------------------
# Figure
# -------------------------
fig, axes = plt.subplots(2, 1, figsize=(8.5, 6), sharex=True)

# -------------------------
# FEX
# -------------------------
b1 = axes[0].bar(x - width, fex_0, width, label='0-shot')
b2 = axes[0].bar(x,         fex_2, width, label='2-shot')
b3 = axes[0].bar(x + width, fex_5, width, label='5-shot')

axes[0].set_ylabel('FEX (%)')
axes[0].set_title('FEX Comparison under Different Shots')
axes[0].set_ylim(0, 100)

# ✅ 强制让上面子图也显示横轴 tick labels
axes[0].set_xticks(x)
axes[0].set_xticklabels(llms, rotation=15)
axes[0].tick_params(axis='x', labelbottom=True)  # ⭐关键

# -------------------------
# SEX
# -------------------------
c1 = axes[1].bar(x - width, sex_0, width, label='0-shot')
c2 = axes[1].bar(x,         sex_2, width, label='2-shot')
c3 = axes[1].bar(x + width, sex_5, width, label='5-shot')

axes[1].set_ylabel('SEX (%)')
axes[1].set_title('SEX Comparison under Different Shots')
axes[1].set_ylim(0, 100)

axes[1].set_xticks(x)
axes[1].set_xticklabels(llms, rotation=15)

# -------------------------
# Value labels
# -------------------------
def add_labels(ax, bars):
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h + 1,
                f'{h:.1f}', ha='center', va='bottom', fontsize=8, color='black')

for bars in [b1, b2, b3]:
    add_labels(axes[0], bars)

for bars in [c1, c2, c3]:
    add_labels(axes[1], bars)

# -------------------------
# Legend: figure-level, right side
# -------------------------
handles, labels = axes[0].get_legend_handles_labels()
fig.legend(
    handles,
    labels,
    loc='center left',
    bbox_to_anchor=(0.87, 0.5),
    frameon=True
)

# Leave space for legend
plt.subplots_adjust(right=0.82, hspace=0.55)

plt.savefig('DifferentLLM.png', dpi=300)
plt.show()

import os

filepath = '/Users/pedrohedro/Base-AI-Agentic\/Base-AI-Agentic/templates/index.html'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Adicionar o box de PnL Consolidado no Header
old_trades_box = """                <div class="stat-box">
                    <span class="stat-label">Total Trades</span>
                    <span id="total-trades" class="stat-value font-mono">0</span>
                </div>"""

new_trades_box = """                <div class="stat-box">
                    <span class="stat-label">Total Trades</span>
                    <span id="total-trades" class="stat-value font-mono">0</span>
                </div>

                <div class="stat-box">
                    <span class="stat-label">PnL Consolidado</span>
                    <span id="consolidated-pnl" class="stat-value font-mono pnl-neutral">$0.00</span>
                </div>"""

# 2. Adicionar a legenda na tabela de trades
old_table_end = """                            </tbody>
                        </table>
                    </div>
                </div>"""

new_table_end = """                            </tbody>
                        </table>
                    </div>
                    <p class="table-legend">* PnL para COMPRA (BUY) é estimado / não realizado com base no preço atual. PnL para VENDA (SELL) é realizado.</p>
                </div>"""

if old_trades_box in content:
    content = content.replace(old_trades_box, new_trades_box)
    print("Box de PnL Consolidado adicionado com sucesso no HTML.")
else:
    print("ERRO: Box de Total Trades não encontrado.")

if old_table_end in content:
    content = content.replace(old_table_end, new_table_end)
    print("Legenda da tabela de trades adicionada com sucesso no HTML.")
else:
    print("ERRO: Final da tabela de trades não encontrado.")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Modificação de index.html concluída.")

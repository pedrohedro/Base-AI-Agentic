import os

filepath = '/Users/pedrohedro/Base-AI-Agentic\/Base-AI-Agentic/static/js/app.js'
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Alvo da substituição:
old_target = """            // Histórico de Trades
            if (tradesBodyEl) {
                if (data.trades_history && data.trades_history.length > 0) {
                    // Ordenar por data decrescente (mais recente primeiro)
                    const sortedTrades = [...data.trades_history].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                    
                    tradesBodyEl.innerHTML = sortedTrades.map(trade => {
                        const badgeClass = trade.type === 'BUY' ? 'badge-buy' : 'badge-sell';
                        
                        let pnlText = '-';
                        let pnlClass = 'pnl-neutral';
                        
                        if (trade.type === 'SELL') {
                            const pnlValue = parseFloat(trade.pnl);
                            if (pnlValue > 0) {
                                pnlText = `+$${pnlValue.toFixed(2)}`;
                                pnlClass = 'pnl-profit';
                            } else if (pnlValue < 0) {
                                pnlText = `-$${Math.abs(pnlValue).toFixed(2)}`;
                                pnlClass = 'pnl-loss';
                            } else {
                                pnlText = `$0.00`;
                                pnlClass = 'pnl-neutral';
                            }
                        }
                        
                        return `
                            <tr>
                                <td class="font-mono text-muted text-xs">${trade.timestamp}</td>
                                <td><span class="badge-trade ${badgeClass}">${trade.type}</span></td>
                                <td class="font-mono">${parseFloat(trade.eth_amount).toFixed(5)} ETH</td>
                                <td class="font-mono">${parseFloat(trade.usdc_amount).toFixed(2)} USDC</td>
                                <td class="font-mono text-cyan">$${parseFloat(trade.price).toFixed(2)}</td>
                                <td><span class="pnl-badge ${pnlClass}">${pnlText}</span></td>
                            </tr>
                        `;
                    }).join('');"""

# Nova lógica contendo o cálculo do PnL consolidado e PnL não realizado dos BUYs
new_target = """            // Preço atual do CoinGecko para cálculo de PnL não realizado
            const currentEthPrice = parseFloat(data.coingecko_price) || 0;

            // Calcular PnL Consolidado (Realizado + Não Realizado)
            if (data.trades_history && data.trades_history.length > 0) {
                let realizedPnl = 0;
                let totalEthBought = 0;
                let totalUsdcSpent = 0;
                let totalEthSold = 0;
                let totalUsdcReceived = 0;
                
                data.trades_history.forEach(trade => {
                    if (trade.type === 'SELL') {
                        realizedPnl += parseFloat(trade.pnl) || 0;
                        totalEthSold += parseFloat(trade.eth_amount) || 0;
                        totalUsdcReceived += parseFloat(trade.usdc_amount) || 0;
                    } else if (trade.type === 'BUY') {
                        totalEthBought += parseFloat(trade.eth_amount) || 0;
                        totalUsdcSpent += parseFloat(trade.usdc_amount) || 0;
                    }
                });
                
                const netEthHeld = totalEthBought - totalEthSold;
                const avgBuyPrice = parseFloat(data.average_buy_price) || 0;
                
                let unrealizedPnl = 0;
                if (netEthHeld > 0 && currentEthPrice > 0 && avgBuyPrice > 0) {
                    unrealizedPnl = netEthHeld * (currentEthPrice - avgBuyPrice);
                }
                
                const consolidatedPnl = realizedPnl + unrealizedPnl;
                const pnlEl = document.getElementById('consolidated-pnl');
                if (pnlEl) {
                    if (consolidatedPnl > 0) {
                        pnlEl.textContent = `+$${consolidatedPnl.toFixed(2)}`;
                        pnlEl.className = 'stat-value font-mono pnl-profit';
                    } else if (consolidatedPnl < 0) {
                        pnlEl.textContent = `-$${Math.abs(consolidatedPnl).toFixed(2)}`;
                        pnlEl.className = 'stat-value font-mono pnl-loss';
                    } else {
                        pnlEl.textContent = `$0.00`;
                        pnlEl.className = 'stat-value font-mono pnl-neutral';
                    }
                }
            }

            // Histórico de Trades
            if (tradesBodyEl) {
                if (data.trades_history && data.trades_history.length > 0) {
                    // Ordenar por data decrescente (mais recente primeiro)
                    const sortedTrades = [...data.trades_history].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                    
                    tradesBodyEl.innerHTML = sortedTrades.map(trade => {
                        const badgeClass = trade.type === 'BUY' ? 'badge-buy' : 'badge-sell';
                        
                        let pnlText = '-';
                        let pnlClass = 'pnl-neutral';
                        
                        if (trade.type === 'SELL') {
                            const pnlValue = parseFloat(trade.pnl);
                            if (pnlValue > 0) {
                                pnlText = `+$${pnlValue.toFixed(2)}`;
                                pnlClass = 'pnl-profit';
                            } else if (pnlValue < 0) {
                                pnlText = `-$${Math.abs(pnlValue).toFixed(2)}`;
                                pnlClass = 'pnl-loss';
                            } else {
                                pnlText = `$0.00`;
                                pnlClass = 'pnl-neutral';
                            }
                        } else if (trade.type === 'BUY') {
                            // Calcular PnL não realizado (Paper PnL)
                            const buyPrice = parseFloat(trade.price);
                            const ethAmount = parseFloat(trade.eth_amount);
                            if (currentEthPrice > 0 && buyPrice > 0) {
                                const paperPnl = (currentEthPrice - buyPrice) * ethAmount;
                                if (paperPnl > 0) {
                                    pnlText = `+$${paperPnl.toFixed(4)}*`;
                                    pnlClass = 'pnl-profit';
                                } else if (paperPnl < 0) {
                                    pnlText = `-$${Math.abs(paperPnl).toFixed(4)}*`;
                                    pnlClass = 'pnl-loss';
                                } else {
                                    pnlText = `$0.0000*`;
                                    pnlClass = 'pnl-neutral';
                                }
                            }
                        }
                        
                        return `
                            <tr>
                                <td class="font-mono text-muted text-xs">${trade.timestamp}</td>
                                <td><span class="badge-trade ${badgeClass}">${trade.type}</span></td>
                                <td class="font-mono">${parseFloat(trade.eth_amount).toFixed(5)} ETH</td>
                                <td class="font-mono">${parseFloat(trade.usdc_amount).toFixed(2)} USDC</td>
                                <td class="font-mono text-cyan">$${parseFloat(trade.price).toFixed(2)}</td>
                                <td><span class="pnl-badge ${pnlClass}">${pnlText}</span></td>
                            </tr>
                        `;
                    }).join('');"""

if old_target in content:
    content = content.replace(old_target, new_target)
    print("app.js atualizado com sucesso!")
else:
    print("ERRO: Seção de histórico de trades não encontrada em app.js")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)
print("Modificação concluída.")

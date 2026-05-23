// Elementos DOM
const walletAddressEl = document.getElementById('wallet-address');
const btnCopyAddress = document.getElementById('btn-copy-address');
const walletBalanceEl = document.getElementById('wallet-balance');
const statusPulseEl = document.getElementById('status-pulse');
const statusTextEl = document.getElementById('status-text');
const btnToggleTrading = document.getElementById('btn-toggle-trading');
const infoNetworkEl = document.getElementById('info-network');
const logsContainer = document.getElementById('logs-container');
const btnClearLogs = document.getElementById('btn-clear-logs');
const chatMessagesContainer = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const btnSendChat = document.getElementById('btn-send-chat');

// Novos Elementos para o Histórico de Trades e Saldos
const usdcBalanceEl = document.getElementById('usdc-balance');
const totalWalletValueEl = document.getElementById('total-wallet-value');
const totalWalletBreakdownEl = document.getElementById('total-wallet-breakdown');
const avgBuyPriceEl = document.getElementById('avg-buy-price');
const openPositionEl = document.getElementById('open-position');
const totalTradesEl = document.getElementById('total-trades');
const tradesBodyEl = document.getElementById('trades-body');

// Novos Elementos para Desempenho e Benchmarks
const perfAgentValEl = document.getElementById('perf-agent-val');
const perfAgentUsdEl = document.getElementById('perf-agent-usd');
const perfBeatBadgeEl = document.getElementById('perf-beat-badge');
const perfBhValEl = document.getElementById('perf-bh-val');
const perfBhPricesEl = document.getElementById('perf-bh-prices');
const perfDcaValEl = document.getElementById('perf-dca-val');
const perfDcaUsdEl = document.getElementById('perf-dca-usd');

let currentPerformanceData = null;
let selectedTimeframe = '24h';

// Elementos de Preço dos Oráculos e Tendência
const coingeckoPriceEl = document.getElementById('eth-price-coingecko');
const pythPriceEl = document.getElementById('eth-price-pyth');
const marketTrendBadgeEl = document.getElementById('market-trend-badge');
const marketTrendTextEl = document.getElementById('market-trend-text');


// Configuração do Gráfico Chart.js
const ctx = document.getElementById('priceChart').getContext('2d');
let priceChart;
let priceHistory = [];
let timeLabels = [];

// Histórico de logs rastreados localmente para evitar repetições
let loadedLogsCount = 0;

// Inicializa o Gráfico com dados simulados/reais
function initChart() {
    // Gerar valores base para os últimos 7 períodos
    let basePrice = 3125.00;
    for (let i = 0; i < 7; i++) {
        basePrice += (Math.random() - 0.5) * 20;
        priceHistory.push(basePrice);
        timeLabels.push(getFormattedTimeOffset(7 - i));
    }

    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: timeLabels,
            datasets: [{
                label: 'ETH/USD ($)',
                data: priceHistory,
                borderColor: '#00f0ff',
                backgroundColor: 'rgba(0, 240, 255, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8a90af', font: { size: 9 } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.03)' },
                    ticks: { color: '#8a90af', font: { size: 9 } }
                }
            }
        }
    });
}

function getFormattedTimeOffset(offsetMinutes) {
    const time = new Date(Date.now() - offsetMinutes * 60000);
    return time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// Atualiza o gráfico com um novo preço de ETH
function updateChartPrice(newPrice) {
    priceHistory.shift();
    priceHistory.push(newPrice);
    timeLabels.shift();
    const now = new Date();
    timeLabels.push(now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }));
    
    priceChart.update();
}

// Copiar endereço
btnCopyAddress.addEventListener('click', () => {
    const address = walletAddressEl.textContent;
    if (address && address !== 'Carregando...') {
        navigator.clipboard.writeText(address).then(() => {
            btnCopyAddress.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="#00ff66" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`;
            setTimeout(() => {
                btnCopyAddress.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`;
            }, 2000);
        });
    }
});

// Limpar logs localmente
btnClearLogs.addEventListener('click', () => {
    logsContainer.innerHTML = '<div class="log-line system">Terminal limpo pelo usuário.</div>';
});

// Função para buscar e atualizar logs e status do agente
async function updateAgentData() {
    try {
        // 1. Atualizar Status
        const statusRes = await fetch('/api/status');
        if (statusRes.ok) {
            const data = await statusRes.json();
            
            // Endereço
            if (data.address && data.address !== 'Não inicializado') {
                walletAddressEl.textContent = data.address;
                walletAddressEl.title = data.address;
            } else {
                walletAddressEl.textContent = 'Indisponível';
            }
            
            // Saldo
            walletBalanceEl.textContent = `${parseFloat(data.balance).toFixed(5)} ETH`;
            
            // Saldo USDC
            if (usdcBalanceEl) {
                usdcBalanceEl.textContent = `${parseFloat(data.usdc_balance).toFixed(2)} USDC`;
            }

            // Valor Total da Carteira (ETH + USDC)
            if (totalWalletValueEl) {
                const ethPrice = parseFloat(data.coingecko_price) || 0;
                const ethValue = (parseFloat(data.balance) || 0) * ethPrice;
                const usdcValue = parseFloat(data.usdc_balance) || 0;
                const totalValue = ethValue + usdcValue;
                totalWalletValueEl.textContent = `$${totalValue.toFixed(2)}`;
                
                if (totalWalletBreakdownEl) {
                    totalWalletBreakdownEl.textContent = `$${ethValue.toFixed(2)} ETH + $${usdcValue.toFixed(2)} USDC`;
                }
            }
            
            // Custo Médio
            if (avgBuyPriceEl) {
                avgBuyPriceEl.textContent = `${parseFloat(data.average_buy_price).toFixed(2)} USD`;
            }
            
            // Total Trades
            if (totalTradesEl) {
                totalTradesEl.textContent = data.total_trades;
            }

            // Oráculo, Tendência e Atualização do Gráfico
            if (coingeckoPriceEl && data.coingecko_price) {
                coingeckoPriceEl.textContent = `$${parseFloat(data.coingecko_price).toFixed(2)}`;
            }
            if (pythPriceEl && data.pyth_price) {
                pythPriceEl.textContent = `$${parseFloat(data.pyth_price).toFixed(2)}`;
            }
            if (marketTrendBadgeEl && marketTrendTextEl && data.trend) {
                const trend = data.trend;
                marketTrendBadgeEl.className = `trend-badge ${trend}`;
                
                let trendLabel = 'Lateral';
                if (trend === 'alta') trendLabel = 'Alta';
                else if (trend === 'queda') trendLabel = 'Queda';
                
                marketTrendTextEl.textContent = trendLabel;
            }

            // Atualização do Gráfico com histórico do backend
            if (data.price_history && data.price_history.length > 0) {
                priceHistory = data.price_history.map(item => item.price);
                timeLabels = data.price_history.map(item => {
                    const parts = item.timestamp.split(' ');
                    return parts.length > 1 ? parts[1].substring(0, 5) : item.timestamp;
                });
                
                priceChart.data.labels = timeLabels;
                priceChart.data.datasets[0].data = priceHistory;
                priceChart.update();
            } else {
                // Fallback: se o backend não tiver histórico, atualiza com base no preço atual do CoinGecko se ele mudou
                const currentPrice = parseFloat(data.coingecko_price);
                if (currentPrice > 0 && priceHistory.length > 0 && priceHistory[priceHistory.length - 1] !== currentPrice) {
                    updateChartPrice(currentPrice);
                }
            }

            // Preço atual do CoinGecko para cálculo de PnL não realizado
            const currentEthPrice = parseFloat(data.coingecko_price) || 0;

            let realizedPnl = 0;
            let totalEthBought = 0;
            let totalUsdcSpent = 0;
            let totalEthSold = 0;
            let totalUsdcReceived = 0;
            let netEthHeld = 0;

            // Calcular PnL Consolidado (Realizado + Não Realizado)
            if (data.trades_history && data.trades_history.length > 0) {
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
                netEthHeld = totalEthBought - totalEthSold;
            }

            // Atualizar Posição Aberta
            const displayNetEth = netEthHeld < 0.000001 ? 0 : netEthHeld;
            const openPositionUsdc = displayNetEth * currentEthPrice;
            if (openPositionEl) {
                openPositionEl.textContent = `${displayNetEth.toFixed(5)} ETH ($${openPositionUsdc.toFixed(2)})`;
            }

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
                    }).join('');
                } else {
                    tradesBodyEl.innerHTML = `
                        <tr>
                            <td colspan="6" class="text-center text-muted">Nenhuma operação detectada.</td>
                        </tr>
                    `;
                }
            }
            
            // Rede
            infoNetworkEl.textContent = formatNetworkName(data.network);
            
            // Status Autônomo
            const btnText = btnToggleTrading.querySelector('.btn-text');
            if (data.autonomous_active) {
                statusPulseEl.className = 'status-pulse online';
                statusTextEl.textContent = 'Autônomo';
                statusTextEl.style.color = '#00ff66';
                
                btnToggleTrading.className = 'btn btn-primary btn-glow btn-active';
                btnText.textContent = 'Pausar Trading Autônomo';
            } else {
                statusPulseEl.className = 'status-pulse offline';
                statusTextEl.textContent = 'Manual';
                statusTextEl.style.color = '#ff3366';
                
                btnToggleTrading.className = 'btn btn-primary btn-glow';
                btnText.textContent = 'Ativar Trading Autônomo';
            }
        }

        // 2. Atualizar Logs do Terminal
        const logsRes = await fetch('/api/logs');
        if (logsRes.ok) {
            const logsData = await logsRes.json();
            const logs = logsData.logs;
            
            // Se houver novos logs, atualizar a tela
            if (logs.length > loadedLogsCount) {
                const newLogs = logs.slice(loadedLogsCount);
                newLogs.forEach(log => {
                    const logLine = document.createElement('div');
                    logLine.className = `log-line ${log.category}`;
                    logLine.textContent = `[${log.timestamp}] ${log.message}`;
                    logsContainer.appendChild(logLine);
                    
                    // Se for log de preço de mercado, atualizar gráfico
                    if (log.category === 'market' && log.message.includes('Preço atual do ETH:')) {
                        const priceMatch = log.message.match(/\$(\d+\.\d+)/);
                        if (priceMatch && priceMatch[1]) {
                            updateChartPrice(parseFloat(priceMatch[1]));
                        }
                    }
                });
                
                loadedLogsCount = logs.length;
                // Auto-scroll do terminal
                logsContainer.scrollTop = logsContainer.scrollHeight;
            }
        }
    } catch (err) {
        console.error('Erro de conexão com o backend:', err);
    }
}

function formatNetworkName(net) {
    if (net === 'base-sepolia') return 'Base Sepolia Testnet';
    if (net === 'base-mainnet') return 'Base Mainnet';
    return net;
}

// Lógica de envio de comando via botão de Toggle (Ativar/Desativar loop autônomo)
btnToggleTrading.addEventListener('click', async () => {
    const btnLoader = btnToggleTrading.querySelector('.btn-loader');
    const btnText = btnToggleTrading.querySelector('.btn-text');
    
    btnLoader.classList.remove('hidden');
    btnText.classList.add('hidden');
    btnToggleTrading.disabled = true;

    try {
        const response = await fetch('/api/toggle', { method: 'POST' });
        if (response.ok) {
            await updateAgentData();
        } else {
            const err = await response.json();
            alert(`Erro: ${err.detail}`);
        }
    } catch (err) {
        console.error('Falha de rede ao alternar trading:', err);
    } finally {
        btnLoader.classList.add('hidden');
        btnText.classList.remove('hidden');
        btnToggleTrading.disabled = false;
    }
});

// Lógica do Chat Interativo
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const userMessage = chatInput.value.trim();
    if (!userMessage) return;

    // 1. Limpar input e desativar chat temporariamente
    chatInput.value = '';
    chatInput.disabled = true;
    btnSendChat.disabled = true;

    // 2. Mostrar mensagem do usuário no container
    appendChatMessage('user', 'Você', userMessage);

    // 3. Enviar ao backend FastAPI
    try {
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userMessage })
        });
        
        if (response.ok) {
            const data = await response.json();
            appendChatMessage('agent', 'Base Agentic', data.reply);
        } else {
            const err = await response.json();
            appendChatMessage('agent', 'Base Agentic', `Erro na execução: ${err.detail}`);
        }
    } catch (err) {
        appendChatMessage('agent', 'Base Agentic', 'Erro ao se conectar ao servidor do agente de trading.');
    } finally {
        chatInput.disabled = false;
        btnSendChat.disabled = false;
        chatInput.focus();
        // Recarregar os logs imediatamente após a interação
        updateAgentData();
    }
});

function appendChatMessage(type, sender, text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${type}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'msg-avatar';
    avatar.textContent = type === 'user' ? '👤' : '🤖';
    
    const contentWrapper = document.createElement('div');
    contentWrapper.className = 'msg-content-wrapper';
    
    const senderName = document.createElement('span');
    senderName.className = 'msg-sender';
    senderName.textContent = sender;
    
    const msgText = document.createElement('p');
    msgText.className = 'msg-text';
    msgText.textContent = text;
    
    contentWrapper.appendChild(senderName);
    contentWrapper.appendChild(msgText);
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentWrapper);
    
    chatMessagesContainer.appendChild(messageDiv);
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
}

// --- Lógica de Performance & Benchmarks ---
async function updatePerformanceData() {
    try {
        const response = await fetch('/api/performance');
        if (response.ok) {
            currentPerformanceData = await response.json();
            renderPerformance();
        }
    } catch (err) {
        console.error('Erro ao buscar dados de performance:', err);
    }
}

function renderPerformance() {
    if (!currentPerformanceData || !currentPerformanceData.performance) return;
    
    const data = currentPerformanceData.performance[selectedTimeframe];
    if (!data) return;
    
    // 1. Retorno do Agente
    const agentReturn = parseFloat(data.agent_return);
    const agentPnlUsd = parseFloat(data.agent_pnl_usd);
    
    perfAgentValEl.textContent = `${agentReturn >= 0 ? '+' : ''}${agentReturn.toFixed(2)}%`;
    perfAgentUsdEl.textContent = `${agentPnlUsd >= 0 ? '+$' : '-$'}${Math.abs(agentPnlUsd).toFixed(2)} USD`;
    
    // Classes de cores semânticas para o Agente
    if (agentReturn > 0) {
        perfAgentValEl.className = 'perf-val value-profit';
    } else if (agentReturn < 0) {
        perfAgentValEl.className = 'perf-val value-loss';
    } else {
        perfAgentValEl.className = 'perf-val value-neutral';
    }
    
    // 2. Buy & Hold ETH
    const bhReturn = parseFloat(data.bh_return);
    const startPrice = parseFloat(data.start_price);
    const currentPrice = parseFloat(data.current_price);
    
    perfBhValEl.textContent = `${bhReturn >= 0 ? '+' : ''}${bhReturn.toFixed(2)}%`;
    perfBhPricesEl.textContent = `$${startPrice.toFixed(2)} ➔ $${currentPrice.toFixed(2)}`;
    
    if (bhReturn > 0) {
        perfBhValEl.className = 'perf-val value-profit';
    } else if (bhReturn < 0) {
        perfBhValEl.className = 'perf-val value-loss';
    } else {
        perfBhValEl.className = 'perf-val value-neutral';
    }
    
    // 3. DCA Diário ETH
    const dcaReturn = parseFloat(data.dca_return);
    const dcaPnlUsd = parseFloat(data.dca_pnl_usd);
    
    perfDcaValEl.textContent = `${dcaReturn >= 0 ? '+' : ''}${dcaReturn.toFixed(2)}%`;
    perfDcaUsdEl.textContent = `${dcaPnlUsd >= 0 ? '+$' : '-$'}${Math.abs(dcaPnlUsd).toFixed(2)} USD`;
    
    if (dcaReturn > 0) {
        perfDcaValEl.className = 'perf-val value-profit';
    } else if (dcaReturn < 0) {
        perfDcaValEl.className = 'perf-val value-loss';
    } else {
        perfDcaValEl.className = 'perf-val value-neutral';
    }
    
    // 4. Badge Outperform
    // O agente bateu ambos se o retorno dele for estritamente superior ao B&H e ao DCA
    if (agentReturn > bhReturn && agentReturn > dcaReturn) {
        perfBeatBadgeEl.classList.remove('hidden');
    } else {
        perfBeatBadgeEl.classList.add('hidden');
    }
}

// --- Lógica de Futuros Perpétuos (Hyperliquid) ---
async function updateFuturesData() {
    try {
        const response = await fetch('/api/futures/state');
        if (response.ok) {
            const data = await response.json();
            
            // 1. Atualizar Cards de Margem
            const fAccountValueEl = document.getElementById('f-account-value');
            const fAvailableMarginEl = document.getElementById('f-available-margin');
            const fPositionMarginEl = document.getElementById('f-position-margin');
            const fUnrealizedPnlEl = document.getElementById('f-unrealized-pnl');
            
            if (fAccountValueEl) fAccountValueEl.textContent = `$${parseFloat(data.account_value).toFixed(2)}`;
            if (fAvailableMarginEl) fAvailableMarginEl.textContent = `$${parseFloat(data.available_margin).toFixed(2)}`;
            if (fPositionMarginEl) fPositionMarginEl.textContent = `$${parseFloat(data.position_margin).toFixed(2)}`;
            
            if (fUnrealizedPnlEl) {
                const pnl = parseFloat(data.unrealized_pnl) || 0.0;
                if (pnl > 0) {
                    fUnrealizedPnlEl.textContent = `+$${pnl.toFixed(2)}`;
                    fUnrealizedPnlEl.className = 'f-stat-value pnl-profit';
                } else if (pnl < 0) {
                    fUnrealizedPnlEl.textContent = `-$${Math.abs(pnl).toFixed(2)}`;
                    fUnrealizedPnlEl.className = 'f-stat-value pnl-loss';
                } else {
                    fUnrealizedPnlEl.textContent = `$0.00`;
                    fUnrealizedPnlEl.className = 'f-stat-value pnl-neutral';
                }
            }
            
            // Atualizar o faucet com o endereço atual da carteira se carregado
            const walletAddrText = walletAddressEl.textContent;
            const faucetAddrEl = document.getElementById('agent-wallet-addr-faucet');
            if (faucetAddrEl && walletAddrText && walletAddrText !== 'Carregando...') {
                faucetAddrEl.textContent = walletAddrText;
            }
            
            // 2. Renderizar Posições Ativas
            const positionsBodyEl = document.getElementById('futures-positions-body');
            if (positionsBodyEl) {
                if (data.positions && data.positions.length > 0) {
                    positionsBodyEl.innerHTML = data.positions.map(pos => {
                        const sideClass = pos.side === 'LONG' ? 'long' : 'short';
                        
                        let pnlText = '$0.00';
                        let pnlClass = 'pnl-neutral';
                        const pnlVal = parseFloat(pos.unrealizedPnl) || 0.0;
                        if (pnlVal > 0) {
                            pnlText = `+$${pnlVal.toFixed(2)}`;
                            pnlClass = 'pnl-profit';
                        } else if (pnlVal < 0) {
                            pnlText = `-$${Math.abs(pnlVal).toFixed(2)}`;
                            pnlClass = 'pnl-loss';
                        }
                        
                        let targetText = 'Nenhum';
                        if (pos.sl || pos.tp) {
                            targetText = '';
                            if (pos.sl) targetText += `SL: $${parseFloat(pos.sl).toFixed(2)}<br>`;
                            if (pos.tp) targetText += `TP: $${parseFloat(pos.tp).toFixed(2)}`;
                        }
                        
                        return `
                            <tr>
                                <td class="bold">${pos.coin}-PERP</td>
                                <td><span class="badge-dir ${sideClass}">${pos.side}</span></td>
                                <td class="font-mono">${parseFloat(pos.szi).toFixed(4)}</td>
                                <td class="font-mono">$${parseFloat(pos.entryPx).toFixed(2)}</td>
                                <td class="font-mono">$${parseFloat(pos.markPx).toFixed(2)}</td>
                                <td class="font-mono">${pos.leverage}x</td>
                                <td><span class="pnl-badge ${pnlClass}">${pnlText}</span></td>
                                <td class="font-mono text-xs text-muted">${targetText}</td>
                                <td>
                                    <button class="btn-close-position" onclick="closePositionManual('${pos.coin}')">
                                        Fechar Posição
                                    </button>
                                </td>
                            </tr>
                        `;
                    }).join('');
                } else {
                    positionsBodyEl.innerHTML = `
                        <tr>
                            <td colspan="9" class="text-center text-muted">Nenhuma posição aberta encontrada.</td>
                        </tr>
                    `;
                }
            }
            
            // 3. Renderizar Histórico de Trades Futuros
            const fTradesBodyEl = document.getElementById('futures-trades-body');
            if (fTradesBodyEl) {
                if (data.trades_history && data.trades_history.length > 0) {
                    const sortedTrades = [...data.trades_history].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
                    fTradesBodyEl.innerHTML = sortedTrades.map(trade => {
                        const typeClass = trade.type.includes('OPEN') ? 'badge-buy' : 'badge-sell';
                        
                        let pnlText = '-';
                        let pnlClass = 'pnl-neutral';
                        const pnlVal = parseFloat(trade.pnl) || 0.0;
                        
                        if (trade.type.includes('CLOSE')) {
                            if (pnlVal > 0) {
                                pnlText = `+$${pnlVal.toFixed(2)}`;
                                pnlClass = 'pnl-profit';
                            } else if (pnlVal < 0) {
                                pnlText = `-$${Math.abs(pnlVal).toFixed(2)}`;
                                pnlClass = 'pnl-loss';
                            } else {
                                pnlText = `$0.00`;
                            }
                        }
                        
                        return `
                            <tr>
                                <td class="font-mono text-muted text-xs">${trade.timestamp}</td>
                                <td class="bold">${trade.coin}-PERP</td>
                                <td><span class="badge-trade ${typeClass}">${trade.type}</span></td>
                                <td class="font-mono">${parseFloat(trade.sz).toFixed(4)}</td>
                                <td class="font-mono text-cyan">$${parseFloat(trade.price).toFixed(2)}</td>
                                <td class="font-mono">${trade.leverage ? trade.leverage + 'x' : '-'}</td>
                                <td class="font-mono">$${parseFloat(trade.margin).toFixed(2)}</td>
                                <td><span class="pnl-badge ${pnlClass}">${pnlText}</span></td>
                            </tr>
                        `;
                    }).join('');
                } else {
                    fTradesBodyEl.innerHTML = `
                        <tr>
                            <td colspan="8" class="text-center text-muted">Nenhum trade de futuros registrado.</td>
                        </tr>
                    `;
                }
            }
        }
    } catch (err) {
        console.error('Erro de conexão ao buscar estado de futuros:', err);
    }
}

window.closePositionManual = async function(asset) {
    if (!confirm(`Tem certeza de que deseja fechar manualmente a posição em ${asset}-PERP?`)) {
        return;
    }
    
    const buttons = document.querySelectorAll('.btn-close-position');
    buttons.forEach(btn => btn.disabled = true);
    
    try {
        const response = await fetch('/api/futures/close_manual', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset: asset })
        });
        
        if (response.ok) {
            const data = await response.json();
            alert(`Sucesso: ${data.message}`);
            await updateFuturesData();
            await updateAgentData();
        } else {
            const err = await response.json();
            alert(`Erro ao fechar posição: ${err.detail}`);
        }
    } catch (err) {
        alert(`Erro de conexão: ${err.message}`);
    } finally {
        buttons.forEach(btn => btn.disabled = false);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    
    const tabBtns = document.querySelectorAll('.tab-btn');
    const spotTabContent = document.getElementById('spot-tab-content');
    const futuresTabContent = document.getElementById('futures-tab-content');
    
    tabBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            tabBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            const tab = btn.dataset.tab;
            if (tab === 'spot') {
                spotTabContent.classList.add('active');
                futuresTabContent.classList.remove('active');
            } else if (tab === 'futures') {
                futuresTabContent.classList.add('active');
                spotTabContent.classList.remove('active');
            }
        });
    });
    
    const btnCopyAddressFaucet = document.getElementById('btn-copy-address-faucet');
    const agentWalletAddrFaucet = document.getElementById('agent-wallet-addr-faucet');
    
    if (btnCopyAddressFaucet && agentWalletAddrFaucet) {
        btnCopyAddressFaucet.addEventListener('click', () => {
            const address = agentWalletAddrFaucet.textContent;
            if (address && address !== 'Carregando...') {
                navigator.clipboard.writeText(address).then(() => {
                    btnCopyAddressFaucet.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="#00ff66" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`;
                    setTimeout(() => {
                        btnCopyAddressFaucet.innerHTML = `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 24 24"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`;
                    }, 2000);
                });
            }
        });
    }

    updateAgentData();
    updateFuturesData();
    
    setInterval(updateAgentData, 3000);
    setInterval(updateFuturesData, 3000);

    const timeframeBtns = document.querySelectorAll('.timeframe-btn');
    timeframeBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            timeframeBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedTimeframe = btn.dataset.window;
            renderPerformance();
        });
    });

    updatePerformanceData();
    setInterval(updatePerformanceData, 15000);
});

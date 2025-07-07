async function initializePage1() {
    const env = await window.electronAPI.getEnvVars();
    // In dev, use relative paths. In prod, use the absolute path with file:// protocol.
    const assetsBasePath = env.isDev ? '../assets' : `file:///${env.assetsPathInProd.replace(/\\/g, '/')}`;

    // --- DIAGNOSTIC LOGGING ---
    console.log('[DIAG] Environment received:', env);
    console.log('[DIAG] Calculated assets base path:', assetsBasePath);

    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    const API_BASE_URL = 'http://127.0.0.1:8000';

    const characterSelect = document.getElementById('character-select');
    const suitSelect = document.getElementById('suit-select');
    const costSelect = document.getElementById('cost-select');
    const mainEntrySelect = document.getElementById('main-entry-select');
    const echoSelect = document.getElementById('echo-select');
    const detailsButton = document.getElementById('details-button');

    let characters = [];
    let suits = [];
    let echoData = {};
    let charMetadata = [];
    let suitMetadata = [];
    let echoMetadata = [];
    let entryStatsData = {};
    let entryCoefData = {};
    let history = [];
    let nextHistoryId = 0;
    let schedulerChart;
    let weightChart;
    let briefAnalysisProb = 0.0;
    let scannedProfiles = [
    ];
    let isWorking = false;
    let historySortBy = 'exp'; // 'exp' or 'tuner'
    let resourceWeights = {
        num_echo: 1.0,
        exp: 1.0,
        tuner: 1.0
    };

    // sort toggle icons
    const sortExpIcon = document.getElementById('sort-exp');
    const sortTunerIcon = document.getElementById('sort-tuner');
    if (sortExpIcon) sortExpIcon.src = `${assetsBasePath}/imgs/exp.png`;
    if (sortTunerIcon) sortTunerIcon.src = `${assetsBasePath}/imgs/tuner.png`;

    const debouncedUpdateAnalysis = debounce(updateAnalysisAndScoreDisplay, 50);

    const schedulerInputs = [
        document.getElementById('scheduler-input-0'),
        document.getElementById('scheduler-input-1'),
        document.getElementById('scheduler-input-2'),
        document.getElementById('scheduler-input-3'),
    ];
    const examplePopup = document.getElementById('example-profile-popup');
    const weightPopup = document.getElementById('weight-popup');
    let hoverTimeout;
    const indexToLevel = [5, 10, 15, 20];

    schedulerInputs.forEach((input, index) => {
        const row = input.closest('.scheduler-control-row');
        if (!row) return;

        row.addEventListener('mouseenter', () => {
            clearTimeout(hoverTimeout);
            hoverTimeout = setTimeout(async () => {
                const prob = parseFloat(input.value) / 100;
                if (isNaN(prob) || prob < 0) return;

                // Position the popup vertically next to the hovered row
                const topPosition = row.offsetTop + row.offsetHeight / 2;
                examplePopup.style.top = `${topPosition}px`;

                examplePopup.innerHTML = '正在查找标准示例...';
                examplePopup.classList.add('visible');

                const payload = {
                    level: indexToLevel[index],
                    prob: prob,
                    coef: userSelection.entry_weights,
                    score_thres: parseFloat(calculateTotalScore()),
                    locked_keys: userSelection.locked_keys
                };

                try {
                    const response = await fetch(`${API_BASE_URL}/api/get_example_profile`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    const result = await response.json();

                    if (result && result.profile) {
                        renderExampleProfile(result.profile, result.actual_prob);
                    } else {
                        console.log(result);
                        examplePopup.innerHTML = '未找到合适的示例。';
                    }
                } catch (error) {
                    console.error("Error fetching example profile:", error);
                    examplePopup.innerHTML = '查询失败。';
                }

            }, 500);
        });

        row.addEventListener('mouseleave', () => {
            clearTimeout(hoverTimeout);
            examplePopup.classList.remove('visible');
        });
    });

    const mainEntryOptions = {
        1: ['不指定主属性', '攻击', '防御', '生命'],
        3: ['不指定主属性', '攻击', '防御', '生命', '导电伤害加成', '湮灭伤害加成', '气动伤害加成', '热熔伤害加成', '冷凝伤害加成', '衍射伤害加成', '共鸣效率'],
        4: ['不指定主属性', '暴击', '暴击伤害', '治疗效果加成']
    };

    const userSelection = {
        character: null,
        suit: null,
        cost: 1,
        main_entry: null,
        echo: null,
        entry_weights: {},
        target_entries: {},
        locked_keys: [],
        discard_scheduler: [0.0, 0.0, 0.0, 0.0]
    };

    async function fetchData() {
        try {
            // --- DIAGNOSTIC LOGGING ---
            const urlsToFetch = {
                char: `${assetsBasePath}/characters.txt`,
                suit: `${assetsBasePath}/suit.txt`,
                echo: `${assetsBasePath}/echo.json`,
                // ... add other urls if needed for debugging
            };
            console.log('[DIAG] Attempting to fetch URLs:', urlsToFetch);

            const [charRes, suitRes, echoRes, metaRes, suitMetaRes, entryStatsRes, entryCoefRes, echoMetaRes] = await Promise.all([
                fetch(urlsToFetch.char),
                fetch(urlsToFetch.suit),
                fetch(urlsToFetch.echo),
                fetch(`${assetsBasePath}/imgs/char/metadata.json`),
                fetch(`${assetsBasePath}/imgs/suit/metadata.json`),
                fetch(`${assetsBasePath}/config/entry_stats.yml`),
                fetch(`${assetsBasePath}/config/entry_coef.yml`),
                fetch(`${assetsBasePath}/imgs/echo/metadata.json`)
            ]);
            
            // --- DIAGNOSTIC LOGGING ---
            console.log(`[DIAG] characters.txt response status: ${charRes.status} (ok: ${charRes.ok})`);
            console.log(`[DIAG] suit.txt response status: ${suitRes.status} (ok: ${suitRes.ok})`);
            console.log(`[DIAG] echo.json response status: ${echoRes.status} (ok: ${echoRes.ok})`);


            if (!charRes.ok || !suitRes.ok || !echoRes.ok || !metaRes.ok || !suitMetaRes.ok || !entryStatsRes.ok || !entryCoefRes.ok || !echoMetaRes.ok) {
                console.error('[DIAG] One or more fetch requests were not OK.');
                throw new Error('Failed to fetch data');
            }

            const charText = await charRes.text();
            // --- DIAGNOSTIC LOGGING ---
            console.log('[DIAG] Raw content from characters.txt:', JSON.stringify(charText));
            
            characters = charText.trim().split(/\r?\n/).map(line => {
                const parts = line.split(' ');
                return { ch: parts[0], en: parts[1] };
            });
            // --- DIAGNOSTIC LOGGING ---
            console.log('[DIAG] Parsed characters array:', characters);

            const suitText = await suitRes.text();
            suits = suitText.trim().split(/\r?\n/).map(line => line.trim());

            echoData = await echoRes.json();
            
            const metaData = await metaRes.json();
            charMetadata = metaData.characters;
            
            const suitMetaData = await suitMetaRes.json();
            suitMetadata = suitMetaData;

            const entryStatsText = await entryStatsRes.text();
            entryStatsData = jsyaml.load(entryStatsText);

            echoMetadata = await echoMetaRes.json();

            // Add a "0" value option to each entry's distribution
            for (const key in entryStatsData) {
                if (entryStatsData.hasOwnProperty(key)) {
                    entryStatsData[key].distribution.unshift({ value: 0, probability: 0 });
                }
            }

            const entryCoefText = await entryCoefRes.text();
            entryCoefData = jsyaml.load(entryCoefText);

        } catch (error) {
            console.error("Error fetching data:", error);
        }
    }

    function populateDropdowns() {
        // --- DIAGNOSTIC LOGGING ---
        console.log('[DIAG] Populating dropdowns with characters:', characters);
        characters.forEach(char => {
            if(char && char.ch && char.en){
                const option = document.createElement('option');
                option.value = char.en;
                option.textContent = char.ch;
                characterSelect.appendChild(option);
            }
        });

        suits.forEach(suit => {
            if(suit){
                const option = document.createElement('option');
                option.value = suit;
                option.textContent = suit;
                suitSelect.appendChild(option);
            }
        });
    }
    
    function updateMainEntryOptions() {
        const selectedCost = costSelect.value;
        mainEntrySelect.innerHTML = '';
        
        const options = mainEntryOptions[selectedCost] || [];
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt;
            option.textContent = opt;
            mainEntrySelect.appendChild(option);
        });
        
        mainEntrySelect.value = '不指定主属性';
        userSelection.main_entry = mainEntrySelect.value;
        mainEntrySelect.disabled = !characterSelect.value || !suitSelect.value;
    }

    function updateEchoes() {
        const selectedSuit = suitSelect.value;
        const selectedCost = parseInt(costSelect.value, 10);
        
        echoSelect.innerHTML = '';
        userSelection.echo = null;

        const noneOption = document.createElement('option');
        noneOption.value = "";
        noneOption.textContent = "不指定声骸";
        echoSelect.appendChild(noneOption);
        echoSelect.value = "";

        if (selectedSuit && selectedCost) {
            const filteredEchos = Object.entries(echoData).filter(([name, data]) => {
                return data.cost === selectedCost && data.suit.includes(selectedSuit);
            }).map(([name]) => name);

            if (filteredEchos.length > 0) {
                echoSelect.disabled = false;

                filteredEchos.forEach(echo => {
                    const option = document.createElement('option');
                    option.value = echo;
                    option.textContent = echo;
                    echoSelect.appendChild(option);
                });
            }
        }
    }
    
    function checkSelectionsAndToggleOptions() {
        const enabled = characterSelect.value && suitSelect.value;
        
        costSelect.disabled = !enabled;
        mainEntrySelect.disabled = !enabled;
        detailsButton.disabled = !enabled;
        detailsButton.title = enabled ? "" : "请先选择角色和声骸套装";

        if (enabled) {
            updateMainEntryOptions();
            updateEchoes();
        } else {
            mainEntrySelect.innerHTML = '';
            const mainEntryDefault = document.createElement('option');
            mainEntryDefault.textContent = '不指定主属性';
            mainEntrySelect.appendChild(mainEntryDefault);
            
            echoSelect.innerHTML = '';
            const echoDefault = document.createElement('option');
            echoDefault.value = '';
            echoDefault.disabled = true;
            echoDefault.selected = true;
            echoDefault.textContent = '目标声骸';
            echoSelect.appendChild(echoDefault);
            echoSelect.disabled = true;
        }
    }

    function getCharCoef(charEnName) {
        const coefs = { ...entryCoefData.Default.coef };
        const charData = entryCoefData[charEnName];
        
        if (charData) {
            if (charData.dmg_source) {
                switch (charData.dmg_source) {
                    case "hp":
                        coefs.hp_num = 0.00676;
                        coefs.hp_rate = 1;
                        break;
                    case "atk":
                        coefs.atk_num = 0.1;
                        coefs.atk_rate = 1;
                        break;
                    case "def":
                        coefs.def_num = 0.1;
                        coefs.def_rate = 1;
                        break;
                }
            }
            if (charData.coef) {
                for (const [key, value] of Object.entries(charData.coef)) {
                    coefs[key] = value;
                }
            }
        }
        return coefs;
    }

    function calculateTotalScore() {
        let totalScore = 0;
        for (const [key, value] of Object.entries(userSelection.target_entries)) {
            const weight = userSelection.entry_weights[key] || 0;
            totalScore += value * weight;
        }
        return totalScore.toFixed(2);
    }

    function countNonZeroTargets() {
        return Object.values(userSelection.target_entries).filter(v => v !== 0).length;
    }

    async function updateAnalysisAndScoreDisplay() {
        console.log("Attempting to update analysis and score display...");

        const scoreDisplay = document.getElementById('total-score-display');
        const nonZeroCount = countNonZeroTargets();
        const isValid = nonZeroCount <= 5;
        
        console.log(`Current state: isValid=${isValid}, nonZeroCount=${nonZeroCount}`);

        if (scoreDisplay) {
            scoreDisplay.innerHTML = `总分: ${calculateTotalScore()} <b style="color: ${isValid ? '#2d3748' : '#e53e3e'};">(${nonZeroCount}/5)</b>`;
        }

        document.querySelectorAll('.setting-row, .setting-slider').forEach(el => {
            el.classList.toggle('warning', !isValid);
        });
        
        document.getElementById('close-settings').disabled = !isValid;

        // Analysis part
        if (!isValid) {
            console.log("Analysis skipped: Target count is invalid.");
            const expectedScoreDisplay = document.getElementById('expected-score-display');
            const probDisplay = document.getElementById('prob-above-threshold-display');
            if (expectedScoreDisplay) expectedScoreDisplay.textContent = '期望得分: N/A';
            if (probDisplay) probDisplay.textContent = '达标概率: N/A';
            return;
        }
    
        const scoreThres = parseFloat(calculateTotalScore());
    
        try {
            console.log("Sending request to /api/get_brief_analysis with score threshold:", scoreThres);
            const response = await fetch(`${API_BASE_URL}/api/get_brief_analysis`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    coef: userSelection.entry_weights,
                    score_thres: scoreThres,
                    locked_keys: userSelection.locked_keys
                })
            });
    
            if (!response.ok) {
                console.error(`HTTP error! status: ${response.status}`);
                throw new Error(`HTTP error! status: ${response.status}`);
            }
    
            const result = await response.json();
            console.log("Received analysis from backend:", result);
    
            briefAnalysisProb = result.prob_above_threshold;

            const expectedScoreDisplay = document.getElementById('expected-score-display');
            const probDisplay = document.getElementById('prob-above-threshold-display');
    
            if (expectedScoreDisplay) {
                expectedScoreDisplay.textContent = `期望得分: ${result.expected_score.toFixed(2)}`;
            }
            if (probDisplay) {
                probDisplay.textContent = `达标概率: ${(result.prob_above_threshold * 100).toFixed(2)}%`;
            }
    
        } catch (error) {
            console.error("Error fetching analysis:", error);
            const expectedScoreDisplay = document.getElementById('expected-score-display');
            const probDisplay = document.getElementById('prob-above-threshold-display');
            if (expectedScoreDisplay) expectedScoreDisplay.textContent = '期望得分: N/A';
            if (probDisplay) probDisplay.textContent = '达标概率: N/A';
        }
    }

    function initializeScheduler() {
        const canvas = document.getElementById('scheduler-chart');
        const ctx = canvas.getContext('2d');
        const inputs = [
            document.getElementById('scheduler-input-0'),
            document.getElementById('scheduler-input-1'),
            document.getElementById('scheduler-input-2'),
            document.getElementById('scheduler-input-3'),
        ];
    
        const xLabels = ['5-9', '10-14', '15-19', '20-24'];
        let points = userSelection.discard_scheduler; // Stored as 0-1
    
        let draggingPointIndex = -1;
        let isPanning = false;
        let lastMouseY = 0;
        const PADDING = 0.05;
        let yRange = { min: -PADDING, max: 1 + PADDING };
    
        function resizeCanvas() {
            const container = canvas.parentElement;
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            draw();
        }
    
        const padding = { top: 20, right: 20, bottom: 40, left: 40 };
        const chartWidth = () => canvas.width - padding.left - padding.right;
        const chartHeight = () => canvas.height - padding.top - padding.bottom;
    
        const valueToX = (index) => padding.left + (chartWidth() / (points.length - 1)) * index;
        const valueToY = (value) => padding.top + chartHeight() * (1 - (value - yRange.min) / (yRange.max - yRange.min));
        const yToValue = (y) => ((1 - (y - padding.top) / chartHeight()) * (yRange.max - yRange.min)) + yRange.min;
    
        function getNiceStep(range, ticks) {
            const roughStep = range / (ticks - 1);
            const goodSteps = [0.001, 0.002, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.2, 0.25, 0.5, 1];
            const step = goodSteps.reduce((prev, curr) => 
                Math.abs(curr - roughStep) < Math.abs(prev - roughStep) ? curr : prev
            );
            return step;
        }

        function draw() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.fillStyle = '#2c3e50';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            // Draw grid lines and Y labels dynamically
            ctx.strokeStyle = '#34495e';
            ctx.fillStyle = '#bdc3c7';
            ctx.font = '12px sans-serif';
            ctx.lineWidth = 1;

            const range = yRange.max - yRange.min;
            let precision;
            if (range <= 0.005) {
                precision = 3;
            } else if (range <= 0.05) {
                precision = 2;
            } else if (range <= 0.5) {
                precision = 1;
            } else {
                precision = 0;
            }

            const step = getNiceStep(yRange.max - yRange.min, 5);
            const startValue = Math.floor(yRange.min / step) * step;
            
            for (let value = startValue; value < yRange.max; value += step) {
                if (value < yRange.min) continue; // Don't draw labels below the range
                const y = valueToY(value);
                ctx.beginPath();
                ctx.moveTo(padding.left, y);
                ctx.lineTo(canvas.width - padding.right, y);
                ctx.stroke();
                ctx.fillText(`${(value * 100).toFixed(precision)}%`, padding.left - 35, y + 4);
            }
    
            // Draw X labels
            xLabels.forEach((label, i) => {
                const x = valueToX(i);
                ctx.fillText(label, x - 15, canvas.height - padding.bottom + 20);
            });
    
            ctx.save();

            // Draw line with glow
            ctx.strokeStyle = '#5dade2'; // Lighter, softer blue
            ctx.lineWidth = 2;
            ctx.shadowColor = 'rgba(93, 173, 226, 0.7)';
            ctx.shadowBlur = 12;
            ctx.shadowOffsetY = 4;
            ctx.beginPath();
            points.forEach((p, i) => {
                const x = valueToX(i);
                const y = valueToY(p);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.stroke();
    
            // Draw points with glow
            points.forEach((p, i) => {
                ctx.fillStyle = (i === draggingPointIndex) ? '#f1c40f' : '#5dade2';
                ctx.beginPath();
                const x = valueToX(i);
                const y = valueToY(p);
                ctx.arc(x, y, 7, 0, 2 * Math.PI);
                ctx.fill();
            });

            ctx.restore();
        }
    
        function updateAllPoints(newPoints) {
            newPoints.forEach((p, i) => updatePoint(i, p, false));
            draw();
        }

        function updatePoint(index, value, shouldDraw = true) {
            const clampedValue = Math.max(0, Math.min(1, value));
            points[index] = clampedValue;
            inputs[index].value = (clampedValue * 100).toFixed(2);
            userSelection.discard_scheduler[index] = clampedValue;
            if(shouldDraw) draw();
        }
    
        inputs.forEach((input, index) => {
            input.addEventListener('change', () => {
                const value = parseFloat(input.value) / 100;
                updatePoint(index, value);
            });
        });
    
        canvas.addEventListener('mousedown', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
    
            // Check for point dragging first
            let clickedOnPoint = false;
            for (let i = 0; i < points.length; i++) {
                const pointX = valueToX(i);
                const pointY = valueToY(points[i]);
                const distance = Math.sqrt((mouseX - pointX) ** 2 + (mouseY - pointY) ** 2);
                if (distance < 10) {
                    draggingPointIndex = i;
                    clickedOnPoint = true;
                    break;
                }
            }

            // If not dragging a point, start panning
            if (!clickedOnPoint) {
                isPanning = true;
                lastMouseY = mouseY;
            }
            
            canvas.classList.add('grabbing');
        });
    
        canvas.addEventListener('mousemove', (e) => {
            const rect = canvas.getBoundingClientRect();
            const mouseY = e.clientY - rect.top;
            
            if (draggingPointIndex !== -1) {
                const newValue = yToValue(mouseY);
                updatePoint(draggingPointIndex, newValue);
            } else if (isPanning) {
                const deltaY = mouseY - lastMouseY;
                const valueDelta = (deltaY / chartHeight()) * (yRange.max - yRange.min);
                
                let newMin = yRange.min + valueDelta;
                let newMax = yRange.max + valueDelta;
                
                // Prevent panning beyond the padded boundaries
                if (newMin < -PADDING) {
                    const overshoot = -PADDING - newMin;
                    newMin += overshoot;
                    newMax += overshoot;
                }
                if (newMax > 1 + PADDING) {
                    const overshoot = newMax - (1 + PADDING);
                    newMin -= overshoot;
                    newMax -= overshoot;
                }
                
                yRange.min = newMin;
                yRange.max = newMax;
                draw();
                lastMouseY = mouseY;
            }
        });
    
        canvas.addEventListener('mouseup', () => {
            draggingPointIndex = -1;
            isPanning = false;
            canvas.classList.remove('grabbing');
            draw();
        });

        canvas.addEventListener('mouseleave', () => {
            if (draggingPointIndex !== -1 || isPanning) {
                draggingPointIndex = -1;
                isPanning = false;
                canvas.classList.remove('grabbing');
                draw();
            }
        });

        canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomIntensity = 0.1;
            const rect = canvas.getBoundingClientRect();
            const mouseY = e.clientY - rect.top;
            
            // Prevent zoom if mouse is outside chart area vertically
            if (mouseY < padding.top || mouseY > canvas.height - padding.bottom) return;
            
            const mouseValue = yToValue(mouseY);

            const direction = e.deltaY < 0 ? 1 : -1;
            
            let newRangeSpan = (yRange.max - yRange.min) * (1 - direction * zoomIntensity);

            // Prevent zooming in beyond the limit (0.1%)
            if (direction === 1 && newRangeSpan < 0.001) {
                newRangeSpan = 0.001;
            }
            
            let newMin = mouseValue - (mouseValue - yRange.min) * (newRangeSpan / (yRange.max - yRange.min));
            let newMax = newMin + newRangeSpan;

            // Clamp to boundaries
            if (newRangeSpan >= 1 + 2 * PADDING) {
                yRange.min = -PADDING;
                yRange.max = 1 + PADDING;
            } else if (newMin < -PADDING) {
                yRange.min = -PADDING;
                yRange.max = -PADDING + newRangeSpan;
            } else if (newMax > 1 + PADDING) {
                yRange.max = 1 + PADDING;
                yRange.min = 1 + PADDING - newRangeSpan;
            } else {
                yRange.min = newMin;
                yRange.max = newMax;
            }
            
            draw();
        });

        window.addEventListener('resize', debounce(resizeCanvas, 100));
        resizeCanvas();

        return {
            updateAllPoints,
        }
    }

    function initializeWeightChart() {
        const weightPopup = document.getElementById('weight-popup');
        
        const oldChartContainer = document.getElementById('weight-chart-container');
        if (oldChartContainer) oldChartContainer.remove();
    
        const wrapper = document.createElement('div');
        wrapper.id = 'weight-chart-container';
        wrapper.style.cssText = 'display: flex; align-items: center; justify-content: center; width: 100%; padding: 10px 20px 70px; box-sizing: border-box; gap: 30px; position: relative;';
    
        const chartContainer = document.createElement('div');
        const svgChart = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svgChart.id = 'weight-chart';
        svgChart.setAttribute('width', '300');
        svgChart.setAttribute('height', '300');
        svgChart.setAttribute('viewBox', '0 0 300 300');
        chartContainer.appendChild(svgChart);
    
        const slidersContainer = document.createElement('div');
        slidersContainer.style.cssText = 'display: flex; flex-direction: column; gap: 20px; width: 200px;';
    
        ['num_echo', 'exp', 'tuner'].forEach(key => {
            const labels = { num_echo: '声骸数量', exp: '经验值', tuner: '调谐器' };
            const group = document.createElement('div');
            group.style.cssText = 'display: flex; flex-direction: column;';
            const labelRow = document.createElement('div');
            labelRow.style.cssText = 'display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;';
            const label = document.createElement('label');
            label.textContent = labels[key];
            label.style.cssText = 'color: #E0E0E0; font-size: 14px; font-weight: 500;';
            const valueSpan = document.createElement('span');
            valueSpan.id = `weight-value-${key}`;
            valueSpan.style.cssText = 'color: #FFFFFF; font-size: 14px; font-weight: 600;';
            const slider = document.createElement('input');
            slider.type = 'range';
            slider.id = `weight-slider-${key}`;
            slider.min = 0;
            slider.max = 1000;
            slider.className = 'weight-slider';
            labelRow.append(label, valueSpan);
            group.append(labelRow, slider);
            slidersContainer.appendChild(group);
        });
    
        wrapper.append(chartContainer, slidersContainer);
        weightPopup.prepend(wrapper);
    
        const sliders = {
            num_echo: document.getElementById('weight-slider-num_echo'),
            exp: document.getElementById('weight-slider-exp'),
            tuner: document.getElementById('weight-slider-tuner')
        };
        const valueSpans = {
            num_echo: document.getElementById('weight-value-num_echo'),
            exp: document.getElementById('weight-value-exp'),
            tuner: document.getElementById('weight-value-tuner')
        };
        const keys = ['num_echo', 'exp', 'tuner'];
        const centerX = 150, centerY = 150, radius = 120, innerRadius = 40;
        
        let isDragging = false;
        let dragBoundaryIndex = -1;
        let dragStartAngle = 0;
        let dragStartWeights = {};
    
        function draw() {
            svgChart.innerHTML = '';
            
            const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
            const gradients = [
                { id: 'grad1', colors: ['#4facfe', '#00f2fe'] },
                { id: 'grad2', colors: ['#f093fb', '#f5576c'] },
                { id: 'grad3', colors: ['#ffecd2', '#fcb69f'] }
            ];
            gradients.forEach(grad => {
                const g = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
                g.id = grad.id;
                g.setAttribute('x1', '0%'); g.setAttribute('y1', '0%');
                g.setAttribute('x2', '100%'); g.setAttribute('y2', '100%');
                const s1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
                s1.setAttribute('offset', '0%'); s1.setAttribute('stop-color', grad.colors[0]);
                const s2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
                s2.setAttribute('offset', '100%'); s2.setAttribute('stop-color', grad.colors[1]);
                g.append(s1, s2); defs.appendChild(g);
            });
            const filter = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
            filter.id = 'glow';
            const feBlur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
            feBlur.setAttribute('stdDeviation', '4'); feBlur.setAttribute('result', 'coloredBlur');
            const feMerge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
            const n1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
            n1.setAttribute('in', 'coloredBlur');
            const n2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
            n2.setAttribute('in', 'SourceGraphic');
            feMerge.append(n1, n2); filter.appendChild(feBlur); filter.appendChild(feMerge);
            defs.appendChild(filter);
            svgChart.appendChild(defs);
    
            const weights = [resourceWeights.num_echo, resourceWeights.exp, resourceWeights.tuner];
            const fillColors = ['url(#grad1)', 'url(#grad2)', 'url(#grad3)'];
            const labels = ['声骸数量', '经验值', '调谐器'];
            let currentAngle = -Math.PI / 2;
    
            weights.forEach((weight, index) => {
                if (weight < 1e-6) return;
    
                const angle = weight * 2 * Math.PI;
                const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    
                if (Math.abs(weight - 1.0) < 1e-6) {
                    const d = `M ${centerX} ${centerY - radius} A ${radius} ${radius} 0 1 1 ${centerX-0.01} ${centerY - radius} L ${centerX-0.01} ${centerY-innerRadius} A ${innerRadius} ${innerRadius} 0 1 0 ${centerX} ${centerY-innerRadius} Z`;
                    path.setAttribute('d', d);
                } else {
                    const endAngle = currentAngle + angle;
                    const largeArc = angle > Math.PI ? 1 : 0;
                    const x1 = centerX + radius * Math.cos(currentAngle);
                    const y1 = centerY + radius * Math.sin(currentAngle);
                    const x2 = centerX + radius * Math.cos(endAngle);
                    const y2 = centerY + radius * Math.sin(endAngle);
                    const x3 = centerX + innerRadius * Math.cos(endAngle);
                    const y3 = centerY + innerRadius * Math.sin(endAngle);
                    const x4 = centerX + innerRadius * Math.cos(currentAngle);
                    const y4 = centerY + innerRadius * Math.sin(currentAngle);
                    path.setAttribute('d', `M ${x1} ${y1} A ${radius} ${radius} 0 ${largeArc} 1 ${x2} ${y2} L ${x3} ${y3} A ${innerRadius} ${innerRadius} 0 ${largeArc} 0 ${x4} ${y4} Z`);
                }
                
                path.setAttribute('fill', fillColors[index]);
                path.style.cursor = 'pointer';
                path.style.transition = 'transform 0.2s ease-out';
                path.addEventListener('mouseenter', () => { path.setAttribute('filter', 'url(#glow)'); path.style.transform = `scale(1.03)`; path.style.transformOrigin = 'center'; });
                path.addEventListener('mouseleave', () => { path.removeAttribute('filter'); path.style.transform = ''; });
                svgChart.appendChild(path);
    
                const labelAngle = currentAngle + angle / 2;
                const labelRadius = (radius + innerRadius) / 2;
                const labelX = centerX + labelRadius * Math.cos(labelAngle);
                const labelY = centerY + labelRadius * Math.sin(labelAngle);
                
                const text = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                text.setAttribute('x', labelX); text.setAttribute('y', labelY - 8);
                text.setAttribute('text-anchor', 'middle'); text.setAttribute('dominant-baseline', 'middle');
                text.style.cssText = 'fill: white; font-size: 16px; font-weight: 600; pointer-events: none;';
                text.textContent = labels[index];
                
                const percentText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
                percentText.setAttribute('x', labelX); percentText.setAttribute('y', labelY + 10);
                percentText.setAttribute('text-anchor', 'middle'); percentText.setAttribute('dominant-baseline', 'middle');
                percentText.style.cssText = 'fill: rgba(255, 255, 255, 0.9); font-size: 14px; pointer-events: none;';
                percentText.textContent = `${(weight * 100).toFixed(1)}%`;
                
                svgChart.appendChild(text);
                svgChart.appendChild(percentText);
    
                currentAngle += angle;
            });
        }
        
        function updateUI() {
            const total = keys.reduce((sum, key) => sum + resourceWeights[key], 0);
            if(total > 0) keys.forEach(key => resourceWeights[key] /= total);
            
            keys.forEach(key => {
                valueSpans[key].textContent = `${(resourceWeights[key] * 100).toFixed(1)}%`;
                sliders[key].value = Math.round(resourceWeights[key] * 1000);
            });
            draw();
        }
    
        function handleSliderInput(changedKey) {
            const newValue = parseFloat(sliders[changedKey].value) / 1000;
            const oldValue = resourceWeights[changedKey];
            const diff = newValue - oldValue;
            const otherKeys = keys.filter(k => k !== changedKey);
            const sumOfOthers = otherKeys.reduce((sum, k) => sum + resourceWeights[k], 0);
    
            resourceWeights[changedKey] = newValue;
            if (sumOfOthers > 1e-6) {
                otherKeys.forEach(key => {
                    resourceWeights[key] -= diff * (resourceWeights[key] / sumOfOthers);
                });
            } else {
                otherKeys.forEach(key => resourceWeights[key] = (1 - newValue) / 2);
            }
            updateUI();
        }
    
        function getAngleFromPoint(x, y) {
            return (Math.atan2(y - centerY, x - centerX) + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI);
        }
    
        svgChart.addEventListener('mousedown', (e) => {
            const rect = svgChart.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const distance = Math.sqrt((x - centerX) ** 2 + (y - centerY) ** 2);
            
            if (distance < innerRadius - 5 || distance > radius + 5) return;
    
            dragStartAngle = getAngleFromPoint(x, y);
            dragStartWeights = JSON.parse(JSON.stringify(resourceWeights));
            
            let cumulativeAngle = 0;
            const boundaries = keys.map(key => {
                cumulativeAngle += resourceWeights[key] * 2 * Math.PI;
                return cumulativeAngle;
            });
            
            let minDistance = Infinity;
            dragBoundaryIndex = -1;
            boundaries.forEach((boundary, index) => {
                let dist = Math.abs(dragStartAngle - boundary);
                if (dist > Math.PI) dist = 2 * Math.PI - dist;
                
                if (dist < minDistance && dist < 0.35) {
                    minDistance = dist;
                    dragBoundaryIndex = index;
                }
            });
            if (dragBoundaryIndex !== -1) {
                isDragging = true;
                e.preventDefault();
            }
        });
    
        document.addEventListener('mousemove', (e) => {
            if (!isDragging) return;
            const rect = svgChart.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const currentAngle = getAngleFromPoint(x, y);
    
            let angleDiff = currentAngle - dragStartAngle;
            if (angleDiff > Math.PI) angleDiff -= 2 * Math.PI;
            if (angleDiff < -Math.PI) angleDiff += 2 * Math.PI;
            
            const percentageDiff = angleDiff / (2 * Math.PI);
            
            const newWeights = JSON.parse(JSON.stringify(dragStartWeights));
            const k1_idx = dragBoundaryIndex;
            const k2_idx = (dragBoundaryIndex - 1 + keys.length) % keys.length;
            const k1 = keys[k1_idx];
            const k2 = keys[k2_idx];
    
            newWeights[k1] -= percentageDiff;
            newWeights[k2] += percentageDiff;
            
            let sum = 0;
            for(const key of keys) {
                newWeights[key] = Math.max(0, Math.min(1, newWeights[key]));
                sum += newWeights[key];
            }
    
            for(const key of keys) {
                if (sum > 1e-6) newWeights[key] /= sum;
            }
    
            resourceWeights = newWeights;
            updateUI();
        });
    
        document.addEventListener('mouseup', () => {
            if (isDragging) {
                isDragging = false;
                dragBoundaryIndex = -1;
            }
        });
    
        keys.forEach(key => sliders[key].addEventListener('input', () => handleSliderInput(key)));
        updateUI();
    
        return { draw: updateUI };
    }

    function renderDetailedSettings() {
        const container = document.getElementById('detailed-settings-container');
        container.innerHTML = '';
        
        // Use saved weights if they exist, otherwise calculate defaults
        let coefs;
        if (Object.keys(userSelection.entry_weights).length > 0) {
            coefs = userSelection.entry_weights;
        } else {
            coefs = getCharCoef(userSelection.character);
            userSelection.entry_weights = coefs; // Store initial weights
        }

        for (const [key, entry] of Object.entries(entryStatsData)) {
            const row = document.createElement('div');
            row.className = 'setting-row';

            // Add lock icon
            const lockIcon = document.createElement('i');
            lockIcon.className = 'mdi mdi-lock-open lock-icon';
            lockIcon.dataset.key = key;
            
            // Check if this key is locked
            if (userSelection.locked_keys.includes(key)) {
                lockIcon.classList.remove('mdi-lock-open');
                lockIcon.classList.add('mdi-lock', 'locked');
            }

            const nameLabel = document.createElement('label');
            nameLabel.className = 'setting-name';
            nameLabel.textContent = entry.name;

            const weightInput = document.createElement('input');
            weightInput.type = 'number';
            weightInput.className = 'setting-weight-input';
            weightInput.value = coefs[key] || 0;
            weightInput.step = 0.1;

            const updateRowStyle = () => {
                const weight = parseFloat(weightInput.value);
                if (weight !== 0) {
                    row.classList.add('has-weight');
                    row.classList.remove('is-zero-weight');
                    // Enable lock icon when weight is not zero
                    lockIcon.classList.remove('disabled');
                } else {
                    row.classList.remove('has-weight');
                    row.classList.add('is-zero-weight');
                    // Disable lock icon when weight is zero and unlock if locked
                    lockIcon.classList.add('disabled');
                    if (lockIcon.classList.contains('locked')) {
                        toggleLock(lockIcon);
                    }
                }
            };
            
            weightInput.addEventListener('change', (e) => {
                userSelection.entry_weights[key] = parseFloat(e.target.value);
                console.log('Weights updated:', userSelection.entry_weights);
                updateRowStyle();
            });
            
            const sliderContainer = document.createElement('div');
            sliderContainer.className = 'slider-container';
            
            const slider = document.createElement('input');
            slider.type = 'range';
            slider.className = 'setting-slider';
            slider.min = 0;
            slider.max = entry.distribution.length - 1;
            slider.step = 1;
            
            // Set slider initial value from saved state or to 0
            const savedValue = userSelection.target_entries[key];
            const savedIndex = savedValue !== undefined 
                ? entry.distribution.findIndex(d => d.value === savedValue) 
                : -1;
            slider.value = (savedIndex !== -1) ? savedIndex : 0;

            const valueLabel = document.createElement('span');
            valueLabel.className = 'slider-value-label';
            
            const updateValueLabel = () => {
                const selectedValue = entry.distribution[slider.value].value;
                valueLabel.textContent = selectedValue + (entry.type === 'percentage' ? '%' : '');
                userSelection.target_entries[key] = selectedValue;
                updateRowStyle();
            };

            slider.addEventListener('input', updateValueLabel);

            // Add lock click handler
            const toggleLock = (icon) => {
                const key = icon.dataset.key;
                // Allow unlocking even if disabled (e.g., when weight is set to 0),
                // but prevent locking a disabled item.
                if (icon.classList.contains('disabled') && !icon.classList.contains('locked')) {
                    return;
                }

                let lockStateChanged = false;

                if (icon.classList.contains('locked')) {
                    // UNLOCK
                    icon.classList.remove('mdi-lock', 'locked');
                    icon.classList.add('mdi-lock-open');
                    const index = userSelection.locked_keys.indexOf(key);
                    if (index > -1) {
                        userSelection.locked_keys.splice(index, 1);
                        lockStateChanged = true;
                    }
                } else {
                    // LOCK
                    // 1. Check against max locked items
                    if (userSelection.locked_keys.length >= 5) {
                        console.warn("Cannot lock more than 5 entries.");
                        return;
                    }

                    // 2. Ensure weight is not zero
                    const weight = parseFloat(weightInput.value) || 0;
                    if (weight === 0) {
                         console.warn("Cannot lock an entry with zero weight.");
                         return;
                    }

                    icon.classList.remove('mdi-lock-open');
                    icon.classList.add('mdi-lock', 'locked');
                    if (!userSelection.locked_keys.includes(key)) {
                        userSelection.locked_keys.push(key);
                        lockStateChanged = true;
                    }
                }

                if (lockStateChanged) {
                    console.log('Locked keys updated:', userSelection.locked_keys);

                    // Reset full analysis results and clear history
                    probResult.textContent = 'N/A';
                    expResult.textContent = 'N/A';
                    if (tunerResult) tunerResult.textContent = 'N/A';
                    history = [];
                    renderHistory();

                    // Update analysis immediately
                    debouncedUpdateAnalysis();
                }
            };

            lockIcon.addEventListener('click', () => toggleLock(lockIcon));

            sliderContainer.append(slider, valueLabel);
            row.append(lockIcon, nameLabel, weightInput, sliderContainer);
            container.appendChild(row);
            
            // Initial updates
            updateValueLabel();
            updateRowStyle();
        }
        debouncedUpdateAnalysis();
    }

    function updateAvatar(selectedCharEn) {
        const avatarContainer = document.querySelector('.avatar-container');
        const characterData = characters.find(c => c.en === selectedCharEn);
        const selectedCharCh = characterData ? characterData.ch : '';
        const character = charMetadata.find(c => c.name === selectedCharCh);
        let avatarImg = document.getElementById('character-avatar');
        const placeholderIcon = avatarContainer.querySelector('.mdi-account');

        if (character && character.file) {
            if (placeholderIcon) placeholderIcon.style.display = 'none';
            
            const imgPath = `${assetsBasePath}/imgs/char/${character.file}`;
            if (!avatarImg) {
                avatarImg = document.createElement('img');
                avatarImg.id = 'character-avatar';
                avatarContainer.appendChild(avatarImg);
            }
            avatarImg.src = imgPath;
            avatarImg.alt = selectedCharCh;
            avatarImg.style.display = 'block';
        } else {
            if (avatarImg) avatarImg.style.display = 'none';
            if (placeholderIcon) placeholderIcon.style.display = 'flex';
        }
    }

    function updateSuitIcon(selectedSuit) {
        const avatarContainer = document.querySelector('.avatar-container');
        let suitIcon = document.getElementById('suit-icon');

        if (selectedSuit) {
            const suit = suitMetadata.find(s => s.name === selectedSuit);
            if (suit && suit.file) {
                const imgPath = `${assetsBasePath}/imgs/suit/${suit.file}`;
                if (!suitIcon) {
                    suitIcon = document.createElement('img');
                    suitIcon.id = 'suit-icon';
                    avatarContainer.appendChild(suitIcon);
                }
                suitIcon.src = imgPath;
                suitIcon.alt = selectedSuit;
                suitIcon.style.display = 'block';
            }
        } else if (suitIcon) {
            suitIcon.style.display = 'none';
        }
    }

    characterSelect.addEventListener('change', (e) => {
        userSelection.character = e.target.value;
        // Reset detailed settings when character changes
        userSelection.entry_weights = {};
        userSelection.target_entries = {};
        userSelection.locked_keys = [];
        checkSelectionsAndToggleOptions();
        updateAvatar(e.target.value);
        console.log('Selection updated:', userSelection);
    });

    suitSelect.addEventListener('change', (e) => {
        userSelection.suit = e.target.value;
        checkSelectionsAndToggleOptions();
        updateSuitIcon(e.target.value);
        console.log('Selection updated:', userSelection);
    });

    costSelect.addEventListener('change', () => {
        userSelection.cost = parseInt(costSelect.value, 10);
        updateMainEntryOptions();
        updateEchoes();
        applyFilterBtn.classList.remove('btn-success');
    });
    
    mainEntrySelect.addEventListener('change', () => {
        userSelection.main_entry = mainEntrySelect.value;
        updateEchoes();
        applyFilterBtn.classList.remove('btn-success');
    });

    echoSelect.addEventListener('change', (e) => {
        userSelection.echo = e.target.value;
        console.log('Selection updated:', userSelection);
        applyFilterBtn.classList.remove('btn-success');
    });

    const applyButton = document.getElementById('apply-scheduler-button');
    const probResult = document.getElementById('scheduler-prob');
    const expResult = document.getElementById('scheduler-exp');
    const tunerResult = document.getElementById('scheduler-tuner');

    applyButton.addEventListener('click', async () => {
        applyButton.disabled = true;
        const originalContent = applyButton.innerHTML;
        applyButton.innerHTML = `<i class="mdi mdi-loading mdi-spin"></i> 处理中...`;

        const scoreThres = parseFloat(calculateTotalScore());
        const payload = {
            coef: userSelection.entry_weights,
            score_thres: scoreThres,
            scheduler: userSelection.discard_scheduler,
            locked_keys: userSelection.locked_keys
        };

        try {
            const response = await fetch(`${API_BASE_URL}/api/get_full_analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            probResult.textContent = `${(result.prob_above_threshold_with_discard * 100).toFixed(2)}%`;
            
            const wastedExp = result.expected_total_wasted_exp;
            const wastedTuner = result.expected_total_wasted_tuner;
            
            // Add to history
            history.unshift({
                id: `history-${nextHistoryId++}`,
                scheduler: [...userSelection.discard_scheduler],
                prob: result.prob_above_threshold_with_discard,
                exp: wastedExp,
                tuner: wastedTuner
            });
            if (history.length > 50) history.pop(); // Keep history size manageable
            renderHistory();

            if (wastedExp === -1 || wastedExp > 1e9) {
                expResult.textContent = '无穷大';
            } else {
                expResult.textContent = Math.round(wastedExp).toLocaleString();
            }

            // Update tuner result display
            if (tunerResult) {
                if (wastedTuner === undefined) {
                    tunerResult.textContent = 'N/A';
                } else if (wastedTuner === -1 || wastedTuner > 1e9) {
                    tunerResult.textContent = '无穷大';
                } else {
                    tunerResult.textContent = Math.round(wastedTuner).toLocaleString();
                }
            }

            if (wastedExp !== 0) {
                updateScannedEchosAnalysis();
            } else {
                document.getElementById('scanned-echos-panel').style.display = 'none';
            }

        } catch (error) {
            console.error("Error fetching full analysis:", error);
            probResult.textContent = '计算失败';
            expResult.textContent = '计算失败';
            if (tunerResult) tunerResult.textContent = '计算失败';
        } finally {
            applyButton.disabled = false;
            applyButton.innerHTML = originalContent;
        }
    });

    await fetchData();
    populateDropdowns();
    checkSelectionsAndToggleOptions();

    const settingsOverlay = document.getElementById('settings-overlay');
    const closeSettingsButton = document.getElementById('close-settings');
    const detailsButtonIcon = detailsButton.querySelector('.mdi');

    settingsOverlay.addEventListener('change', (event) => {
        if (event.target.closest('#detailed-settings-container')) {
            // Reset full analysis results and history on any setting change
            probResult.textContent = 'N/A';
            expResult.textContent = 'N/A';
            if (tunerResult) tunerResult.textContent = 'N/A';
            history = [];
            renderHistory();

            scannedProfiles.forEach(p => p.analysis = null);
            if (document.getElementById('scanned-echos-panel').style.display !== 'none') {
                renderScannedEchos();
            }

            debouncedUpdateAnalysis();
        }
    });

    detailsButton.addEventListener('click', () => {
        renderDetailedSettings();
        settingsOverlay.classList.add('visible');
        detailsButton.classList.remove('settings-applied');
        detailsButtonIcon.classList.remove('mdi-check');
        detailsButtonIcon.classList.add('mdi-cog');
    });

    closeSettingsButton.addEventListener('click', () => {
        settingsOverlay.classList.remove('visible');
        detailsButton.classList.add('settings-applied');
        detailsButtonIcon.classList.remove('mdi-cog');
        detailsButtonIcon.classList.add('mdi-check');

        const schedulerPanel = document.getElementById('scheduler-panel');
        if (schedulerPanel.style.display === 'none') {
            schedulerPanel.style.display = 'flex';
            // A one-time initialization
            if (!schedulerPanel.dataset.initialized) {
                schedulerChart = initializeScheduler();
                weightChart = initializeWeightChart();
                schedulerPanel.dataset.initialized = 'true';
            }
        }
    });

    detailsButton.addEventListener('mouseenter', () => {
        if (detailsButton.classList.contains('settings-applied')) {
            detailsButtonIcon.classList.remove('mdi-check');
            detailsButtonIcon.classList.add('mdi-cog');
        }
    });

    detailsButton.addEventListener('mouseleave', () => {
        if (detailsButton.classList.contains('settings-applied')) {
            detailsButtonIcon.classList.remove('mdi-cog');
            detailsButtonIcon.classList.add('mdi-check');
        }
    });

    function renderHistory() {
        const historyList = document.getElementById('history-list');
        
        // --- FLIP Animation: Step 1 - Get old positions ---
        const oldPositions = {};
        historyList.querySelectorAll('.history-item').forEach(item => {
            if (item.dataset.id) {
                oldPositions[item.dataset.id] = item.getBoundingClientRect();
            }
        });

        const sortedHistory = [...history].sort((a, b) => {
            const key = historySortBy === 'tuner' ? 'tuner' : 'exp';
            const valA = a[key];
            const valB = b[key];
            if (valA === -1 && valB === -1) return 0;
            if (valA === -1) return 1;
            if (valB === -1) return -1;
            return valA - valB;
        });

        // --- Temporarily detach list to prevent reflows while building ---
        const parent = historyList.parentNode;
        parent.removeChild(historyList);
        historyList.innerHTML = '';

        const newElements = [];
        sortedHistory.forEach(item => {
            const div = document.createElement('div');
            div.className = 'history-item';
            div.dataset.id = item.id;

            const expVal = item.exp === -1 ? '∞' : Math.round(item.exp).toLocaleString();
            const expValDisplay = item.exp === -1 ? '∞' : Math.round(item.exp / 5000).toLocaleString();
            const tunerVal = (item.tuner === undefined || item.tuner === -1) ? '∞' : Math.round(item.tuner).toLocaleString();

            const expIcon = `${assetsBasePath}/imgs/exp.png`;
            const tunerIcon = `${assetsBasePath}/imgs/tuner.png`;

            div.innerHTML = `
                <div class="history-value"><img src="${expIcon}"><span class="history-pill">${expValDisplay}</span></div>
                <div class="history-value"><img src="${tunerIcon}"><span class="history-pill">${tunerVal}</span></div>
            `;

            div.addEventListener('click', () => {
                historyList.querySelectorAll('.history-item').forEach(el => el.classList.remove('selected'));
                div.classList.add('selected');

                userSelection.discard_scheduler = [...item.scheduler];
                if (schedulerChart) {
                    schedulerChart.updateAllPoints(userSelection.discard_scheduler);
                }
                probResult.textContent = `${(item.prob * 100).toFixed(2)}%`;
                expResult.textContent = expVal;
                if (tunerResult) tunerResult.textContent = tunerVal;

                updateScannedEchosAnalysis();
            });
            newElements.push(div);
            historyList.appendChild(div);
        });

        // --- Re-attach list ---
        parent.appendChild(historyList);

        // --- FLIP Animation: Step 2, 3, 4 - Last, Invert, Play ---
        newElements.forEach(item => {
            const id = item.dataset.id;
            const oldPos = oldPositions[id];
            
            if (oldPos) { // An existing item that may have moved
                const newPos = item.getBoundingClientRect();
                const deltaX = oldPos.left - newPos.left;
                const deltaY = oldPos.top - newPos.top;

                if (Math.abs(deltaX) > 0.5 || Math.abs(deltaY) > 0.5) {
                    item.style.transform = `translate(${deltaX}px, ${deltaY}px)`;
                    item.style.transition = 'transform 0s';
    
                    requestAnimationFrame(() => {
                        item.style.transform = '';
                        item.style.transition = 'transform 0.5s cubic-bezier(0.4, 0, 0.2, 1)';
                    });
                }
            } else { // A new item, animate its appearance
                item.style.opacity = '0';
                item.style.transform = 'scale(0.9)';
                requestAnimationFrame(() => {
                    item.style.opacity = '1';
                    item.style.transform = 'scale(1)';
                    item.style.transition = 'opacity 0.4s ease, transform 0.4s cubic-bezier(0.4, 0, 0.2, 1)';
                });
            }

            // Clean up transition style to avoid conflicts
            item.addEventListener('transitionend', () => {
                item.style.transition = '';
            }, { once: true });
        });
    }

    function renderEchoDetails(originalIndex) {
        const detailsContainer = document.getElementById('scanned-echo-details-container');
        if (originalIndex === -1 || !scannedProfiles[originalIndex]) {
            detailsContainer.style.display = 'none';
            return;
        }
        detailsContainer.style.display = 'flex';
    
        const item = scannedProfiles[originalIndex];
        const { profile, analysis } = item;
    
        const entriesList = document.getElementById('echo-detail-entries');
        entriesList.innerHTML = '';
        for (const [key, value] of Object.entries(profile)) {
            if (key !== 'level' && key !== 'name' && value) {
                const entryName = entryStatsData[key] ? entryStatsData[key].name : key;
                const entryType = entryStatsData[key] ? entryStatsData[key].type : '';
                const li = document.createElement('li');

                const nameSpan = document.createElement('span');
                nameSpan.className = 'entry-name';
                nameSpan.textContent = entryName;

                const valueSpan = document.createElement('span');
                valueSpan.className = 'entry-value';
                valueSpan.textContent = `${value}${entryType === 'percentage' ? '%' : ''}`;

                li.appendChild(nameSpan);
                li.appendChild(valueSpan);
                entriesList.appendChild(li);
            }
        }
    
        const maxProbEl = document.getElementById('echo-detail-max-prob');
        const probEl = document.getElementById('echo-detail-prob');
        const expEl = document.getElementById('echo-detail-exp');
        const tunerEl = document.getElementById('echo-detail-tuner');
        const scoreEl = document.getElementById('echo-detail-score');
        const expectedScoreEl = document.getElementById('echo-detail-expected-score');
    
        if (analysis) {
            maxProbEl.textContent = `${(analysis.prob_above_threshold * 100).toFixed(2)}%`;
            probEl.textContent = `${(analysis.prob_above_threshold_with_discard * 100).toFixed(2)}%`;
            const wastedExp = analysis.expected_total_wasted_exp;
            const wastedTuner = analysis.expected_total_wasted_tuner;
            if (wastedExp === -1 || wastedExp > 1e9) {
                expEl.textContent = '无穷大';
            } else {
                expEl.textContent = Math.round(wastedExp).toLocaleString();
            }
            if (tunerEl) {
                if (wastedTuner === undefined) {
                    tunerEl.textContent = 'N/A';
                } else if (wastedTuner === -1 || wastedTuner > 1e9) {
                    tunerEl.textContent = '无穷大';
                } else {
                    tunerEl.textContent = Math.round(wastedTuner).toLocaleString();
                }
            }
            scoreEl.textContent = analysis.score.toFixed(2);
            expectedScoreEl.textContent = analysis.expected_score.toFixed(2);
        } else {
            maxProbEl.textContent = 'N/A';
            probEl.textContent = 'N/A';
            expEl.textContent = 'N/A';
            if (tunerEl) tunerEl.textContent = 'N/A';
            scoreEl.textContent = 'N/A';
            expectedScoreEl.textContent = 'N/A';
        }
    }
    
    function renderScannedEchos(selectedOriginalIndex = -1) {
        const panel = document.getElementById('scanned-echos-panel');
        const listContainer = document.getElementById('scanned-echos-list');
    
        const sortedProfiles = [...scannedProfiles].sort((a, b) => {
            if (!a.analysis) return 1;
            if (!b.analysis) return -1;
            const expA = a.analysis.expected_total_wasted_exp;
            const expB = b.analysis.expected_total_wasted_exp;
            if (expA === -1 && expB === -1) return 0;
            if (expA === -1) return 1;
            if (expB === -1) return -1;
            return expA - expB;
        });
    
        if (selectedOriginalIndex === -1 && sortedProfiles.length > 0) {
            selectedOriginalIndex = scannedProfiles.indexOf(sortedProfiles[0]);
        }
    
        listContainer.innerHTML = '';
        sortedProfiles.forEach(item => {
            const originalIndex = scannedProfiles.indexOf(item);
            const card = document.createElement('div');
            card.className = 'echo-card';
            card.dataset.index = originalIndex;

            if (item.analysis) {
                if (isEchoDiscarded(item)) {
                    card.classList.add('discarded');
                }
                const prob = item.analysis.prob_above_threshold_with_discard;
                if (prob === 1) {
                    card.classList.add('achieved');
                } else if (prob === 0) {
                    card.classList.add('failed');
                }
            }
    
            const echoMeta = echoMetadata.find(e => e.name === item.profile.name);
            if (echoMeta && echoMeta.file) {
                const img = document.createElement('img');
                img.src = `${assetsBasePath}/imgs/echo/${echoMeta.file}`;
                img.alt = item.profile.name;
                img.className = 'echo-card-img';
                card.appendChild(img);
            }
    
            const levelDiv = document.createElement('div');
            levelDiv.className = 'echo-card-level';
            levelDiv.textContent = `Lv. ${item.profile.level}`;
            card.appendChild(levelDiv);
    
            if (originalIndex === selectedOriginalIndex) {
                card.classList.add('selected');
            }
    
            card.addEventListener('click', () => {
                renderScannedEchos(originalIndex);
            });
    
            listContainer.appendChild(card);
        });
    
        renderEchoDetails(selectedOriginalIndex);
        panel.style.display = 'flex';
    }

    async function updateScannedEchosAnalysis() {
        const scoreThres = parseFloat(calculateTotalScore());
    
        const promises = scannedProfiles.map(item => {
            const payload = {
                coef: userSelection.entry_weights,
                score_thres: scoreThres,
                scheduler: userSelection.discard_scheduler,
                profile: item.profile,
                locked_keys: userSelection.locked_keys
            };
            return fetch(`${API_BASE_URL}/api/get_full_analysis`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            }).then(res => res.ok ? res.json() : Promise.reject(`HTTP error! status: ${res.status}`));
        });
    
        try {
            const results = await Promise.all(promises);
            results.forEach((result, index) => {
                scannedProfiles[index].analysis = result;
            });
            renderScannedEchos();
        } catch (error) {
            console.error("Error fetching analysis for scanned echos:", error);
        }
    }

    const applyFilterBtn = document.getElementById('apply-filter-btn');
    applyFilterBtn.addEventListener('click', async () => {
        applyFilterBtn.disabled = true;
        applyFilterBtn.classList.remove('btn-success');
        applyFilterBtn.classList.remove('btn-danger');
        const payload = {
            cost: userSelection.cost,
            suit: userSelection.suit || "",
            echo: userSelection.echo || "",
            main_entry: userSelection.main_entry || ""
        };
        try {
            const response = await fetch(`${API_BASE_URL}/api/apply_filter`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const result = await response.json();
            if (result.success) {
                applyFilterBtn.classList.add('btn-success');
            }
            console.log('Filter applied:', result.success);
        } catch (error) {
            console.error("Error applying filter:", error);
            applyFilterBtn.classList.add('btn-danger');
        } finally {
            applyFilterBtn.disabled = false;
            updateWorkButtonState();
        }
    });

    const scanEchosBtn = document.getElementById('scan-echos-btn');
    scanEchosBtn.addEventListener('click', async () => {
        scanEchosBtn.disabled = true;
        scanEchosBtn.classList.remove('btn-success');
        scanEchosBtn.classList.remove('btn-danger');
        try {
            const response = await fetch(`${API_BASE_URL}/api/scan_echo`);
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const profiles = await response.json();
            scannedProfiles = profiles.map(p => ({ profile: p, analysis: null }));
            
            const schedulerPanel = document.getElementById('scheduler-panel');
            if (schedulerPanel.style.display !== 'none') {
                await updateScannedEchosAnalysis();
            } else {
                renderScannedEchos();
            }
            scanEchosBtn.classList.add('btn-success');
            console.log('Echos scanned and updated.');
        } catch (error) {
            console.error("Error scanning echos:", error);
            scanEchosBtn.classList.add('btn-danger');
        } finally {
            scanEchosBtn.disabled = false;
            updateWorkButtonState();
        }
    });

    const startWorkBtn = document.getElementById('start-work-btn');
    startWorkBtn.addEventListener('click', async () => {
        const icon = startWorkBtn.querySelector('i');

        if (isWorking) {
            // --- STOP ACTION ---
            isWorking = false;
            icon.className = 'mdi mdi-loading mdi-spin';
            startWorkBtn.disabled = true;
            
            try {
                await fetch(`${API_BASE_URL}/api/stop_work`, { method: 'POST' });
                console.log('Stop signal sent successfully.');
            } catch (err) {
                console.error('Failed to send stop signal:', err);
            }
            // The loop will exit, and the finally block will reset the button.
            return;
        }

        // --- START ACTION ---
        isWorking = true;
        startWorkBtn.disabled = false;
        startWorkBtn.classList.remove('btn-success', 'btn-danger');
        icon.className = 'mdi mdi-stop-circle-outline'; // Change to stop icon
        
        try {
            while(isWorking) {
                let bestEchoIndex = -1;
                let minExp = 1e9;
    
                scannedProfiles.forEach((item, index) => {
                    if (item.profile.level < 25 && item.analysis && !isEchoDiscarded(item)) {
                        const currentExp = item.analysis.expected_total_wasted_exp;
                        if (currentExp < minExp && currentExp >= 0) {
                            minExp = currentExp;
                            bestEchoIndex = index;
                        }
                    }
                });
    
                let profileToSend = {};
                let upgradedIndex = -1;
    
                if (bestEchoIndex !== -1) {
                    profileToSend = scannedProfiles[bestEchoIndex].profile;
                    upgradedIndex = bestEchoIndex;
                }
    
                if (upgradedIndex !== -1) {
                    renderScannedEchos(upgradedIndex);
                }
    
                // Immediately check if stop was requested
                if (!isWorking) break;
    
                const response = await fetch(`${API_BASE_URL}/api/upgrade_echo`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(profileToSend)
                });
    
                if (!response.ok) throw new Error(`HTTP error ${response.status}`);
                const newProfile = await response.json();
    
                if (!newProfile) throw new Error("Received null profile from server.");
    
                let updatedProfileIndex;
                if (upgradedIndex !== -1) {
                    scannedProfiles[upgradedIndex].profile = newProfile;
                    scannedProfiles[upgradedIndex].analysis = null;
                    updatedProfileIndex = upgradedIndex;
                } else {
                    scannedProfiles.push({ profile: newProfile, analysis: null });
                    updatedProfileIndex = scannedProfiles.length - 1;
                }
    
                await updateScannedEchosAnalysis();
                
                const newAnalysis = scannedProfiles[updatedProfileIndex].analysis;
                if (newProfile.level === 25 && newAnalysis && newAnalysis.prob_above_threshold_with_discard === 1) {
                    isWorking = false; // Task succeeded
                    icon.className = 'mdi mdi-check';
                    startWorkBtn.classList.add('btn-success');
                }
    
                // Check again before sleep
                if (!isWorking) break;
                
                await new Promise(resolve => setTimeout(resolve, 500));
            }
        } catch (error) {
            console.error("Error during upgrade workflow:", error);
            isWorking = false;
            icon.className = 'mdi mdi-alert-circle';
            startWorkBtn.classList.add('btn-danger');
        } finally {
            // This runs on normal exit, stop, error, or success
            isWorking = false;
            // Reset icon only if it wasn't a final state
            if (!startWorkBtn.classList.contains('btn-success') && !startWorkBtn.classList.contains('btn-danger')) {
                 icon.className = 'mdi mdi-play';
            }
            startWorkBtn.disabled = false;
        }
    });

    const defaultParamsBtn = document.getElementById('default-params-btn');
    defaultParamsBtn.addEventListener('click', () => {
        // this is purely empirical 
        const newThreshold = Math.min(1.0, briefAnalysisProb * 1.1);
        if (schedulerChart) {
            schedulerChart.updateAllPoints([newThreshold, newThreshold, newThreshold, newThreshold]);
        }
    });

    const optimalSchedulerBtn = document.getElementById('optimal-scheduler-btn');
    const weightPopupOverlay = document.getElementById('weight-popup-overlay');

    // Show weight popup on button click
    optimalSchedulerBtn.addEventListener('click', () => {
        weightPopup.classList.add('visible');
        weightPopupOverlay.classList.add('visible');
    });

    // Hide weight popup when clicking overlay
    weightPopupOverlay.addEventListener('click', () => {
        weightPopup.classList.remove('visible');
        weightPopupOverlay.classList.remove('visible');
    });

    // Prevent popup from closing when clicking inside it
    weightPopup.addEventListener('click', (e) => {
        e.stopPropagation();
    });

    // Add calculate button to the popup
    const calculateBtn = document.createElement('button');
    calculateBtn.textContent = '计算最优策略';
    calculateBtn.style.cssText = `
        position: absolute;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 25px;
        padding: 12px 30px;
        font-size: 16px;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
    `;
    
    calculateBtn.addEventListener('mouseenter', () => {
        calculateBtn.style.transform = 'translateX(-50%) translateY(-2px)';
        calculateBtn.style.boxShadow = '0 6px 20px rgba(0, 0, 0, 0.3)';
    });
    
    calculateBtn.addEventListener('mouseleave', () => {
        calculateBtn.style.transform = 'translateX(-50%) translateY(0)';
        calculateBtn.style.boxShadow = '0 4px 15px rgba(0, 0, 0, 0.2)';
    });

    calculateBtn.addEventListener('click', async () => {
        calculateBtn.disabled = true;
        const originalContent = calculateBtn.innerHTML;
        calculateBtn.innerHTML = `<i class="mdi mdi-loading mdi-spin"></i> 计算中...`;

        const scoreThres = parseFloat(calculateTotalScore());
        const payload = {
            num_echo_weight: resourceWeights.num_echo,
            exp_weight: resourceWeights.exp,
            tuner_weight: resourceWeights.tuner,
            coef: userSelection.entry_weights,
            score_thres: scoreThres,
            locked_keys: userSelection.locked_keys,
            iterations: 20
        };

        try {
            const response = await fetch(`${API_BASE_URL}/api/get_optimal_scheduler`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            
            // Update the current scheduler with optimal values
            userSelection.discard_scheduler = result.thresholds;
            if (schedulerChart) {
                schedulerChart.updateAllPoints(result.thresholds);
            }

            // Hide the weight popup
            weightPopup.classList.remove('visible');
            weightPopupOverlay.classList.remove('visible');

        } catch (error) {
            console.error("Error calculating optimal scheduler:", error);
        } finally {
            calculateBtn.disabled = false;
            calculateBtn.innerHTML = originalContent;
        }
    });

    weightPopup.appendChild(calculateBtn);

    function updateWorkButtonState() {
        const applyFilterBtn = document.getElementById('apply-filter-btn');
        const scanEchosBtn = document.getElementById('scan-echos-btn');
        const startWorkBtn = document.getElementById('start-work-btn');

        const filterReady = applyFilterBtn.classList.contains('btn-success');
        const scanReady = scanEchosBtn.classList.contains('btn-success');

        startWorkBtn.disabled = !(filterReady && scanReady);
    }

    function isEchoDiscarded(item) {
        if (!item.analysis || item.profile.level >= 25) {
            return false;
        }
    
        const level = item.profile.level;
        const prob = item.analysis.prob_above_threshold;
        const scheduler = userSelection.discard_scheduler;
    
        let threshold;
        if (level >= 5 && level <= 9) {
            threshold = scheduler[0];
        } else if (level >= 10 && level <= 14) {
            threshold = scheduler[1];
        } else if (level >= 15 && level <= 19) {
            threshold = scheduler[2];
        } else if (level >= 20 && level <= 24) {
            threshold = scheduler[3];
        } else {
            return false; // Not in a discardable range
        }
    
        return prob < threshold;
    }

    /* ---------- sort toggle ---------- */
    function updateSortToggle(target) {
        historySortBy = target;
        if (sortExpIcon && sortTunerIcon) {
            sortExpIcon.classList.toggle('selected', target === 'exp');
            sortTunerIcon.classList.toggle('selected', target === 'tuner');
        }
        renderHistory();
    }

    if (sortExpIcon && sortTunerIcon) {
        sortExpIcon.addEventListener('click', () => updateSortToggle('exp'));
        sortTunerIcon.addEventListener('click', () => updateSortToggle('tuner'));
    }

    function renderExampleProfile(profile, actual_prob) {
        let entriesHtml = '';
        for (const [key, value] of Object.entries(profile)) {
            if (key !== 'level' && key !== 'name' && value) {
                const entryName = entryStatsData[key] ? entryStatsData[key].name : key;
                const entryType = entryStatsData[key] ? entryStatsData[key].type : '';
                entriesHtml += `<li><span class="entry-name">${entryName}</span><span class="entry-value">${value}${entryType === 'percentage' ? '%' : ''}</span></li>`;
            }
        }

        examplePopup.innerHTML = `
            <div class="example-profile-header">
                <div>Lv.${profile.level} 声骸示例</div>
                <div style="font-size: 0.8em; color: #bdc3c7;">达标概率: ${(actual_prob * 100).toFixed(2)}%</div>
            </div>
            <ul id="example-profile-entries">${entriesHtml}</ul>
        `;
    }
} 
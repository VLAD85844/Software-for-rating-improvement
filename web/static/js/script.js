document.addEventListener('DOMContentLoaded', function() {
    const statusIndicator = document.getElementById('status-indicator');
    const statusText = document.querySelector('.status-text');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');

    const selectAllBtn = document.getElementById('select-all');
    const deselectAllBtn = document.getElementById('deselect-all');
    const deleteSelectedBtn = document.getElementById('delete-selected');
    const refreshAccountsBtn = document.getElementById('refresh-accounts');
    const accountList = document.getElementById('account-list');
    const totalAccountsCount = document.getElementById('total-accounts-count');
    const selectedAccountsCount = document.getElementById('selected-accounts-count');
    const activeAccountsCount = document.getElementById('active-accounts-count');
    const accountsFileInput = document.getElementById('accounts-file');
    const proxiesFileInput = document.getElementById('proxies-file');
    const urlsFileInput = document.getElementById('urls-file');
    const createChannel = document.getElementById('create-channel').checked;
    const createChannelCheckbox = document.getElementById('create-channel');
    const enableLikesCheckbox = document.getElementById('enable-likes');
    const enableSubscriptionsCheckbox = document.getElementById('enable-subscriptions');
    const enableReferralCheckbox = document.getElementById('enable-referral');
    const humanBehaviorCheckbox = document.getElementById('human-behavior');
    const titlesFileInput = document.getElementById('titles-file');
    const enableTitleSearchCheckbox = document.getElementById('enable-title-search');
    const tagsFileInput = document.getElementById('tags-file');
    const settingsInputs = [
        'watch-duration', 'max-actions', 'human-behavior',
        'enable-likes', 'enable-subscriptions', 'enable-referral',
        'urls-strategy', 'create-channel', 'enable-title-search',
        'threads-count'
    ];
    const clearProfilesBtn = document.getElementById('clear-profiles');

    // Глобальная переменная для отслеживания последнего выбранного индекса
    let lastCheckedIndex = -1;
    let isRangeSelectionMode = false;

    // Элементы очереди
    const addQueueItemBtn = document.getElementById('add-queue-item');
    const clearQueueBtn = document.getElementById('clear-queue');
    const refreshQueueBtn = document.getElementById('refresh-queue');
    const queueForm = document.getElementById('queue-form');
    const saveQueueItemBtn = document.getElementById('save-queue-item');
    const cancelQueueItemBtn = document.getElementById('cancel-queue-item');
    const queueList = document.getElementById('queue-list');

    settingsInputs.forEach(id => {
        document.getElementById(id).addEventListener('change', saveSettings);
    });

    // Функция для обновления состояния чекбоксов
    function updateCheckboxesState() {
        if (createChannelCheckbox.checked) {
            // Если выбрано создание канала, отключаем другие чекбоксы
            enableLikesCheckbox.disabled = true;
            enableSubscriptionsCheckbox.disabled = true;
            enableReferralCheckbox.disabled = true;
            humanBehaviorCheckbox.disabled = true;
        } else {
            // Если создание канала отключено, разрешаем другие чекбоксы
            enableLikesCheckbox.disabled = false;
            enableSubscriptionsCheckbox.disabled = false;
            enableReferralCheckbox.disabled = false;
            humanBehaviorCheckbox.disabled = false;
        }
    }

    loadSettings();
    updateCheckboxesState();
    checkStatus();
    updateStats();
    loadAccounts();
    loadQueue();
    setInterval(checkStatus, 5000);

    startBtn.addEventListener('click', startScript);
    stopBtn.addEventListener('click', stopScript);
    refreshAccountsBtn.addEventListener('click', loadAccounts);
    selectAllBtn.addEventListener('click', selectAllAccounts);
    deselectAllBtn.addEventListener('click', deselectAllAccounts);
    deleteSelectedBtn.addEventListener('click', deleteSelectedAccounts);

    accountsFileInput.addEventListener('change', function() {
        uploadFile(this, 'accounts');
    });

    proxiesFileInput.addEventListener('change', function() {
        uploadFile(this, 'proxies');
    });

    urlsFileInput.addEventListener('change', function() {
        uploadFile(this, 'urls');
    });

    createChannelCheckbox.addEventListener('change', function() {
        updateCheckboxesState();
    });

    clearProfilesBtn.addEventListener('click', clearProfiles);

    // Обработчики событий для очереди
    addQueueItemBtn.addEventListener('click', showQueueForm);
    clearQueueBtn.addEventListener('click', clearQueue);
    refreshQueueBtn.addEventListener('click', loadQueue);
    saveQueueItemBtn.addEventListener('click', saveQueueItem);
    cancelQueueItemBtn.addEventListener('click', hideQueueForm);

    [enableLikesCheckbox, enableSubscriptionsCheckbox, enableReferralCheckbox, humanBehaviorCheckbox].forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            if (this.checked) {
                // Если выбрана любая другая опция, отключаем создание канала
                createChannelCheckbox.checked = false;
                updateCheckboxesState();
            }
        });
    });



    enableTitleSearchCheckbox.addEventListener('change', function() {
        const isEnabled = this.checked;

        // Блокируем реферальные переходы, стратегии URL и создание канала
        document.getElementById('enable-referral').disabled = isEnabled;
        document.getElementById('urls-strategy').disabled = isEnabled;
        document.getElementById('create-channel').disabled = isEnabled;

        // Сбрасываем значения при активации
        if (isEnabled) {
            document.getElementById('enable-referral').checked = false;
            document.getElementById('urls-strategy').value = 'random';
            document.getElementById('create-channel').checked = false;
        }
    });


    function saveSettings() {
        const settings = {
            watchDuration: document.getElementById('watch-duration').value,
            maxActions: document.getElementById('max-actions').value,
            humanBehavior: document.getElementById('human-behavior').checked,
            enableLikes: document.getElementById('enable-likes').checked,
            enableSubscriptions: document.getElementById('enable-subscriptions').checked,
            enableReferral: document.getElementById('enable-referral').checked,
            urlsStrategy: document.getElementById('urls-strategy').value,
            createChannel: document.getElementById('create-channel').checked,
            enableTitleSearch: document.getElementById('enable-title-search').checked,
            threadsCount: document.getElementById('threads-count').value
        };
        localStorage.setItem('youtubeSoftSettings', JSON.stringify(settings));
    }


    function loadSettings() {
        const savedSettings = localStorage.getItem('youtubeSoftSettings');
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            document.getElementById('watch-duration').value = settings.watchDuration;
            document.getElementById('max-actions').value = settings.maxActions;
            document.getElementById('human-behavior').checked = settings.humanBehavior;
            document.getElementById('enable-likes').checked = settings.enableLikes;
            document.getElementById('enable-subscriptions').checked = settings.enableSubscriptions;
            document.getElementById('enable-referral').checked = settings.enableReferral;
            document.getElementById('urls-strategy').value = settings.urlsStrategy;
            document.getElementById('create-channel').checked = settings.createChannel;
            document.getElementById('enable-title-search').checked = settings.enableTitleSearch;
            document.getElementById('threads-count').value = settings.threadsCount || 5;

            updateCheckboxesState();
            
            // Принудительно вызываем обработчик события для чекбокса "Поиск видео по названию"
            if (settings.enableTitleSearch) {
                const titleSearchEvent = new Event('change');
                enableTitleSearchCheckbox.dispatchEvent(titleSearchEvent);
            }
        }
    }

    // Функция для сохранения выбранных аккаунтов
    function saveSelectedAccounts() {
        const selectedAccounts = [];
        document.querySelectorAll('.account-checkbox-input:checked').forEach(checkbox => {
            selectedAccounts.push(checkbox.dataset.id);
        });
        localStorage.setItem('youtubeSoftSelectedAccounts', JSON.stringify(selectedAccounts));
    }

    // Функция для загрузки выбранных аккаунтов
    function loadSelectedAccounts() {
        const savedSelectedAccounts = localStorage.getItem('youtubeSoftSelectedAccounts');
        if (savedSelectedAccounts) {
            const selectedAccountIds = JSON.parse(savedSelectedAccounts);
            document.querySelectorAll('.account-checkbox-input').forEach(checkbox => {
                if (selectedAccountIds.includes(checkbox.dataset.id)) {
                    checkbox.checked = true;
                    const accountItem = checkbox.closest('.account-item');
                    if (accountItem) {
                        accountItem.classList.add('selected');
                    }
                }
            });
            updateAccountsStats();
        }
    }

    async function clearProfiles() {
        try {
            const response = await fetch('/clear_profiles', { method: 'POST' });
            const data = await response.json();
            showToast(data.message, data.status === 'success' ? 'success' : 'error');
        } catch (error) {
            showToast('Ошибка при очистке профилей', 'error');
        }
    }

    function checkStatus() {
        fetch('/status')
            .then(response => response.json())
            .then(data => {
                if (data.is_running) {
                    statusIndicator.classList.add('active');
                    statusIndicator.classList.remove('inactive');
                    statusText.textContent = 'Скрипт запущен';
                    startBtn.disabled = true;
                    stopBtn.disabled = false;
                } else {
                    statusIndicator.classList.add('inactive');
                    statusIndicator.classList.remove('active');
                    statusText.textContent = 'Скрипт остановлен';
                    startBtn.disabled = false;
                    stopBtn.disabled = true;
                }
            })
            .catch(error => {
                console.error('Ошибка при проверке статуса:', error);
            });
    }


    function updateStats() {
        fetch('/stats')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    document.getElementById('total-accounts').textContent = data.stats.total_accounts;
                    document.getElementById('active-accounts').textContent = data.stats.active_accounts;
                    document.getElementById('success-actions').textContent = data.stats.success_actions;
                    document.getElementById('failed-actions').textContent = data.stats.failed_actions;
                } else {
                    // Если нет данных о статистике, используем данные из DOM
                    const totalAccounts = document.querySelectorAll('.account-item').length;
                    const activeAccounts = document.querySelectorAll('.status-active').length;
                    
                    document.getElementById('total-accounts').textContent = totalAccounts;
                    document.getElementById('active-accounts').textContent = activeAccounts;
                    document.getElementById('success-actions').textContent = '0';
                    document.getElementById('failed-actions').textContent = '0';
                }
            })
            .catch(error => {
                console.error('Ошибка при обновлении статистики:', error);
                // В случае ошибки используем данные из DOM
                const totalAccounts = document.querySelectorAll('.account-item').length;
                const activeAccounts = document.querySelectorAll('.status-active').length;
                
                document.getElementById('total-accounts').textContent = totalAccounts;
                document.getElementById('active-accounts').textContent = activeAccounts;
                document.getElementById('success-actions').textContent = '0';
                document.getElementById('failed-actions').textContent = '0';
            });
    }





    function loadAccounts() {
        fetch('/accounts')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Добавляем информацию о прокси к каждому аккаунту
                    Promise.all(data.accounts.map(account => {
                        return fetch(`/accounts/${account.id}/proxy`)
                            .then(res => res.json())
                            .then(proxyData => {
                                account.proxy = proxyData.status === 'success' ? proxyData.proxy : null;
                                return account;
                            });
                    })).then(accountsWithProxies => {
                        renderAccounts(accountsWithProxies);
                        updateAccountsStats();
                        updateStats(); // Обновляем статистику после загрузки аккаунтов
                    });
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки аккаунтов:', error);
            });
    }


    function renderAccounts(accounts) {
        accountList.innerHTML = '';

        if (accounts.length === 0) {
            accountList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-user-slash"></i>
                    <p>Нет загруженных аккаунтов</p>
                </div>
            `;
            return;
        }

        accounts.forEach(account => {
            const accountItem = document.createElement('div');
            accountItem.className = 'account-item';
            accountItem.dataset.id = account.id;
            let tagElement = '';
            if (account.tag) {
                const tagColor = account.tag.color || 'blue';
                tagElement = `<span class="account-tag tag-${tagColor}">${account.tag.name}</span>`;
            }

            accountItem.innerHTML = `
                <div class="account-checkbox">
                    <input type="checkbox" class="account-checkbox-input" data-id="${account.id}">
                </div>
                <div class="account-email" title="${account.email}">
                    ${account.email}
                    ${tagElement}
                </div>
                <div class="account-status ${account.status === 'active' ? 'status-active' : 'status-inactive'}">
                    ${account.status === 'active' ? 'Активен' : 'Неактивен'}
                </div>
                <div class="account-proxy" title="${account.proxy || 'Нет прокси'}">
                    ${account.proxy ? account.proxy.split('@')[0] + '...' : 'Нет прокси'}
                </div>
                <div class="account-actions">
                    <button class="account-action-btn" data-id="${account.id}" title="Удалить">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                    <button class="account-action-btn tag-btn" data-id="${account.id}" title="Изменить метку">
                        <i class="fas fa-tag"></i>
                    </button>
                </div>
            `;
            accountList.appendChild(accountItem);
        });

        // Загружаем сохраненные выбранные аккаунты
        loadSelectedAccounts();
        
        document.querySelectorAll('.account-checkbox-input').forEach((checkbox, index) => {
            // Обработчик одинарного клика для выбора одного элемента
            checkbox.addEventListener('click', function(e) {
                // Если включен режим выделения диапазона, обрабатываем его
                if (isRangeSelectionMode && lastCheckedIndex !== -1) {
                    e.preventDefault();
                    
                    const checkboxes = document.querySelectorAll('.account-checkbox-input');
                    const currentIndex = Array.from(checkboxes).indexOf(this);
                    const start = Math.min(lastCheckedIndex, currentIndex);
                    const end = Math.max(lastCheckedIndex, currentIndex);
                    
                    // Определяем целевое состояние на основе последнего выбранного элемента
                    const lastCheckedBox = checkboxes[lastCheckedIndex];
                    const targetState = !lastCheckedBox.checked;
                    
                    // Выделяем все чекбоксы в диапазоне и добавляем визуальные классы
                    for (let i = start; i <= end; i++) {
                        if (checkboxes[i]) {
                            checkboxes[i].checked = targetState;
                            const accountItem = checkboxes[i].closest('.account-item');
                            if (accountItem) {
                                if (targetState) {
                                    accountItem.classList.add('selected');
                                    accountItem.classList.add('range-selection');
                                } else {
                                    accountItem.classList.remove('selected');
                                    accountItem.classList.remove('range-selection');
                                }
                            }
                        }
                    }
                    
                    // Выключаем режим выделения диапазона
                    isRangeSelectionMode = false;
                    
                    // Убираем визуальную индикацию активного режима
                    document.querySelectorAll('.range-mode-active').forEach(item => {
                        item.classList.remove('range-mode-active');
                    });
                    
                    updateAccountsStats();
                    saveSelectedAccounts();
                }
            });
            
            // Обработчик двойного клика для включения режима выделения диапазона
            checkbox.addEventListener('dblclick', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Включаем режим выделения диапазона
                isRangeSelectionMode = true;
                
                // Обновляем lastCheckedIndex
                lastCheckedIndex = Array.from(document.querySelectorAll('.account-checkbox-input')).indexOf(this);
                
                // Добавляем визуальную индикацию активного режима
                const accountItem = this.closest('.account-item');
                if (accountItem) {
                    accountItem.classList.add('range-mode-active');
                }
                
                // Показываем подсказку пользователю
                showToast('Режим выделения диапазона включен. Кликните на другой аккаунт для завершения выделения.', 'info');
            });
            
            // Обработчик события change для обновления статистики, визуальных классов и lastCheckedIndex
            checkbox.addEventListener('change', function() {
                const accountItem = this.closest('.account-item');
                if (accountItem) {
                    if (this.checked) {
                        accountItem.classList.add('selected');
                        // Обновляем lastCheckedIndex только при установке чекбокса
                        lastCheckedIndex = Array.from(document.querySelectorAll('.account-checkbox-input')).indexOf(this);
                    } else {
                        accountItem.classList.remove('selected');
                        accountItem.classList.remove('range-selection');
                    }
                }
                updateAccountsStats();
                saveSelectedAccounts();
            });
        });

        // Обработчик для чекбокса "Выбрать все" в заголовке
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            selectAllCheckbox.addEventListener('change', function() {
                const checkboxes = document.querySelectorAll('.account-checkbox-input');
                checkboxes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    const accountItem = checkbox.closest('.account-item');
                    if (accountItem) {
                        if (this.checked) {
                            accountItem.classList.add('selected');
                        } else {
                            accountItem.classList.remove('selected');
                            accountItem.classList.remove('range-selection');
                        }
                    }
                });
                updateAccountsStats();
                saveSelectedAccounts();
            });
        }

        document.querySelectorAll('.account-action-btn:not(.tag-btn)').forEach(btn => {
            btn.addEventListener('click', function() {
                const accountId = this.dataset.id;
                deleteAccounts([accountId]);
            });
        });

        document.querySelectorAll('.tag-btn').forEach(btn => {
            btn.addEventListener('click', function() {
                const accountId = this.dataset.id;
                const accountItem = document.querySelector(`.account-item[data-id="${accountId}"]`);
                const currentTag = accountItem.querySelector('.account-tag')?.textContent;
                showTagDialog(accountId, currentTag);
            });
        });

        // Обработчик клика вне чекбоксов для отмены режима выделения диапазона
        document.addEventListener('click', function(e) {
            if (isRangeSelectionMode && !e.target.classList.contains('account-checkbox-input')) {
                isRangeSelectionMode = false;
                document.querySelectorAll('.range-mode-active').forEach(item => {
                    item.classList.remove('range-mode-active');
                });
                showToast('Режим выделения диапазона отменен', 'warning');
            }
        });

        updateAccountsStats();
        updateStats(); // Обновляем статистику после рендеринга аккаунтов
    }


    function updateAccountsStats() {
        const total = document.querySelectorAll('.account-item').length;
        const selected = document.querySelectorAll('.account-checkbox-input:checked').length;
        const active = document.querySelectorAll('.status-active').length;

        totalAccountsCount.textContent = total;
        selectedAccountsCount.textContent = selected;
        activeAccountsCount.textContent = active;
        
        // Обновляем также общую статистику
        document.getElementById('total-accounts').textContent = total;
        document.getElementById('active-accounts').textContent = active;
        
        // Обновляем состояние чекбокса "Выбрать все"
        const selectAllCheckbox = document.getElementById('select-all-checkbox');
        if (selectAllCheckbox) {
            if (selected === 0) {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = false;
            } else if (selected === total) {
                selectAllCheckbox.checked = true;
                selectAllCheckbox.indeterminate = false;
            } else {
                selectAllCheckbox.checked = false;
                selectAllCheckbox.indeterminate = true;
            }
        }
    }


    function selectAllAccounts() {
        document.querySelectorAll('.account-checkbox-input').forEach(checkbox => {
            checkbox.checked = true;
            const accountItem = checkbox.closest('.account-item');
            if (accountItem) {
                accountItem.classList.add('selected');
            }
        });
        updateAccountsStats();
        saveSelectedAccounts(); // Сохраняем состояние выбранных аккаунтов
    }


    function showTagDialog(accountId, currentTag = null) {
        const availableTags = [
            { name: 'Рабочий', value: 'main', color: 'blue' },
            { name: 'Гретый', value: 'reserve', color: 'green' },
            { name: 'Не гретый', value: 'test', color: 'orange' },
            { name: 'С каналом', value: 'vip', color: 'purple' },
            { name: 'Проблемный', value: 'problem', color: 'red' }
        ];

        const dialog = document.createElement('div');
        dialog.className = 'tag-dialog-overlay';
        dialog.style.position = 'fixed';
        dialog.style.top = '0';
        dialog.style.left = '0';
        dialog.style.right = '0';
        dialog.style.bottom = '0';
        dialog.style.backgroundColor = 'rgba(0,0,0,0.5)';
        dialog.style.display = 'flex';
        dialog.style.justifyContent = 'center';
        dialog.style.alignItems = 'center';
        dialog.style.zIndex = '1000';

        const dialogContent = document.createElement('div');
        dialogContent.className = 'tag-dialog-content';
        dialogContent.style.backgroundColor = 'white';
        dialogContent.style.padding = '20px';
        dialogContent.style.borderRadius = '8px';
        dialogContent.style.width = '300px';

        let optionsHTML = availableTags.map(tag => `
            <div class="tag-option ${currentTag === tag.name ? 'selected' : ''}" 
                 data-value="${tag.value}" 
                 data-color="${tag.color}"
                 style="padding: 8px; margin: 5px 0; border-radius: 4px; 
                        background-color: rgba(var(--${tag.color}-color-rgb), 0.1);
                        color: var(--${tag.color}-color); cursor: pointer;">
                ${tag.name}
            </div>
        `).join('');

        dialogContent.innerHTML = `
            <h3 style="margin-top: 0;">Выберите метку для аккаунта</h3>
            <div class="tag-options">
                ${optionsHTML}
            </div>
            <div style="display: flex; justify-content: space-between; margin-top: 20px;">
                <button id="remove-tag-btn" class="btn btn-secondary" style="padding: 8px 16px;">
                    Удалить метку
                </button>
                <button id="cancel-tag-btn" class="btn btn-secondary" style="padding: 8px 16px;">
                    Отмена
                </button>
            </div>
        `;

        dialog.appendChild(dialogContent);
        document.body.appendChild(dialog);

        dialogContent.querySelectorAll('.tag-option').forEach(option => {
            option.addEventListener('click', async function() {
                const tagValue = this.dataset.value;
                const tagName = this.textContent;
                const tagColor = this.dataset.color;

                try {
                    const response = await fetch(`/accounts/${accountId}/tag`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            tag_name: tagName,
                            tag_color: tagColor
                        })
                    });

                    const data = await response.json();
                    if (data.status === 'success') {
                        loadAccounts();
                    } else {
                        showToast(data.message || 'Ошибка обновления метки', 'error');
                    }
                } catch (error) {
                    showToast('Ошибка сети', 'error');
                } finally {
                    document.body.removeChild(dialog);
                }
            });
        });


        dialogContent.querySelector('#remove-tag-btn').addEventListener('click', async function() {
            try {
                const response = await fetch(`/accounts/${accountId}/tag`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        tag_name: null,
                        tag_color: null
                    })
                });

                const data = await response.json();
                if (data.status === 'success') {
                    loadAccounts();
                } else {
                    showToast(data.message || 'Ошибка удаления метки', 'error');
                }
            } catch (error) {
                showToast('Ошибка сети', 'error');
            } finally {
                document.body.removeChild(dialog);
            }
        });

        dialogContent.querySelector('#cancel-tag-btn').addEventListener('click', function() {
            document.body.removeChild(dialog);
        });
    }


    function deselectAllAccounts() {
        document.querySelectorAll('.account-checkbox-input').forEach(checkbox => {
            checkbox.checked = false;
            const accountItem = checkbox.closest('.account-item');
            if (accountItem) {
                accountItem.classList.remove('selected');
                accountItem.classList.remove('range-selection');
            }
        });
        updateAccountsStats();
        saveSelectedAccounts(); // Сохраняем состояние выбранных аккаунтов
    }


    function deleteSelectedAccounts() {
        const selectedIds = Array.from(document.querySelectorAll('.account-checkbox-input:checked'))
            .map(checkbox => checkbox.dataset.id);

        if (selectedIds.length === 0) {
            showToast('Не выбрано ни одного аккаунта', 'warning');
            return;
        }

        deleteAccounts(selectedIds);
    }


    function deleteAccounts(accountIds) {
        fetch('/accounts', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ account_ids: accountIds })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(`Удалено ${data.message} аккаунтов`, 'success');
                loadAccounts();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка при удалении аккаунтов', 'error');
            console.error('Ошибка:', error);
        });
    }


    function startScript() {
        const enableTitleSearch = document.getElementById('enable-title-search').checked;
        const accountCheckboxes = document.querySelectorAll('.account-checkbox-input');
        if (!accountCheckboxes || accountCheckboxes.length === 0) {
            showToast('Нет доступных аккаунтов для запуска', 'warning');
            return;
        }

        const selectedIds = Array.from(accountCheckboxes)
            .filter(checkbox => checkbox.checked)
            .map(checkbox => checkbox.dataset.id);

        if (selectedIds.length === 0) {
            showToast('Не выбрано ни одного аккаунта', 'warning');
            return;
        }

        const threadsCount = document.getElementById('threads-count').value || 5;

        const config = {
            account_ids: selectedIds,
            watch_duration: document.getElementById('watch-duration').value,
            max_actions_per_account: document.getElementById('max-actions').value || 3,
            human_behavior: document.getElementById('human-behavior').checked,
            enable_likes: document.getElementById('enable-likes').checked,
            enable_subscriptions: document.getElementById('enable-subscriptions').checked,
            enable_referral: document.getElementById('enable-referral').checked,
            urls_strategy: document.getElementById('urls-strategy').value || 'random',
            create_channel: document.getElementById('create-channel').checked,
            enable_title_search: enableTitleSearch,
            threads_count: threadsCount
        };

        // Остальной код без изменений
        fetch('/start_script', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(config)
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(`Скрипт успешно запущен. Аккаунты будут обрабатываться группами по ${threadsCount}.`, 'success');
                checkStatus();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка при запуске скрипта', 'error');
            console.error('Ошибка:', error);
        });
    }


    function stopScript() {
        // Показываем подтверждение
        if (!confirm('Вы уверены, что хотите остановить скрипт? Все текущие действия будут прерваны.')) {
            return;
        }

        // Блокируем кнопку на время выполнения запроса
        const stopBtn = document.getElementById('stop-btn');
        stopBtn.disabled = true;
        stopBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Остановка...';

        fetch('/stop_script', {
            method: 'POST'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast('Скрипт остановлен', 'success');
                // Принудительно обновляем статус
                checkStatus();
                updateStats();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка при остановке скрипта', 'error');
            console.error('Ошибка:', error);
        })
        .finally(() => {
            // Восстанавливаем кнопку через 2 секунды
            setTimeout(() => {
                stopBtn.innerHTML = '<i class="fas fa-stop"></i> Стоп';
                stopBtn.disabled = false;
            }, 2000);
        });
    }


    function uploadFile(input, type) {
    const file = input.files[0];
    if (!file) return;

    const uploadBox = document.getElementById(`${type}-upload`);
    const fileInfo = uploadBox.querySelector('.file-info');
    const progressBar = uploadBox.querySelector('.progress');

    fileInfo.textContent = file.name;
    progressBar.style.width = '0%';

    const formData = new FormData();
    formData.append('file', file);

    let endpoint = '';
    switch (type) {
        case 'accounts':
            endpoint = '/accounts';
            break;
        case 'proxies':
            endpoint = '/proxies';
            break;
        case 'urls':
            endpoint = '/urls';
            break;
        case 'titles':
            endpoint = '/titles';
            break;
        case 'tags':
            endpoint = '/tags';
            break;
        default:
            console.error('Unknown upload type:', type);
            return;
    }

    fetch(endpoint, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            progressBar.style.width = '100%';
            showToast(data.message, 'success');

            // Обновляем соответствующие данные после загрузки
            if (type === 'accounts') {
                loadAccounts();
            }
            // Добавляем обработку для тегов
            if (type === 'tags') {
                console.log('Теги успешно загружены:', data.message);
            }
        } else {
            progressBar.style.backgroundColor = 'var(--danger-color)';
            showToast(data.message, 'error');
        }
    })
    .catch(error => {
        progressBar.style.backgroundColor = 'var(--danger-color)';
        showToast('Ошибка загрузки файла', 'error');
        console.error('Ошибка:', error);
    });
}


    function showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        let icon = '';
        if (type === 'success') icon = '<i class="fas fa-check-circle"></i>';
        if (type === 'error') icon = '<i class="fas fa-exclamation-circle"></i>';
        if (type === 'warning') icon = '<i class="fas fa-exclamation-triangle"></i>';

        toast.innerHTML = `${icon}<span>${message}</span>`;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('show');
        }, 10);

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                document.body.removeChild(toast);
            }, 300);
        }, 3000);
    }

    // Функции для работы с очередью
    function showQueueForm() {
        queueForm.style.display = 'block';
        document.getElementById('queue-tag').value = '';
        document.getElementById('queue-title').value = '';
        document.getElementById('queue-filter').value = 'none';
        document.getElementById('queue-priority').value = '0';
    }

    function hideQueueForm() {
        queueForm.style.display = 'none';
    }

    function loadQueue() {
        fetch('/queue')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    renderQueue(data.queue);
                    updateQueueStats();
                } else {
                    showToast(data.message, 'error');
                }
            })
            .catch(error => {
                console.error('Ошибка загрузки очереди:', error);
                showToast('Ошибка загрузки очереди', 'error');
            });
    }

    function renderQueue(queueItems) {
        queueList.innerHTML = '';

        if (queueItems.length === 0) {
            queueList.innerHTML = `
                <div class="empty-state">
                    <i class="fas fa-list"></i>
                    <p>Очередь пуста</p>
                </div>
            `;
            return;
        }

        queueItems.forEach(item => {
            const queueItem = document.createElement('div');
            queueItem.className = 'queue-item';
            queueItem.dataset.id = item.id;

            const priorityClass = item.priority === 1 ? 'high' : item.priority === 2 ? 'critical' : '';
            const priorityText = item.priority === 1 ? 'Высокий' : item.priority === 2 ? 'Критический' : 'Обычный';
            const filterText = getFilterText(item.filter_strategy);

            queueItem.innerHTML = `
                <div class="queue-priority ${priorityClass}">${priorityText}</div>
                <div class="queue-tag">${item.tag}</div>
                <div class="queue-title" title="${item.title}">${item.title}</div>
                <div class="queue-filter">${filterText}</div>
                <div class="queue-status ${item.status}">${getStatusText(item.status)}</div>
                <div class="queue-actions">
                    <button class="queue-action-btn delete" data-id="${item.id}" title="Удалить">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            `;
            queueList.appendChild(queueItem);
        });

        // Добавляем обработчики для кнопок удаления
        document.querySelectorAll('.queue-action-btn.delete').forEach(btn => {
            btn.addEventListener('click', function() {
                const itemId = this.dataset.id;
                deleteQueueItem(itemId);
            });
        });
    }

    function getFilterText(filterStrategy) {
        const filterMap = {
            'none': 'Без фильтров',
            'last-hour': 'За час',
            'today': 'За сегодня',
            'week': 'За неделю',
            'month': 'За месяц'
        };
        return filterMap[filterStrategy] || filterStrategy;
    }

    function getStatusText(status) {
        const statusMap = {
            'pending': 'Ожидает',
            'processing': 'В процессе',
            'completed': 'Завершено',
            'failed': 'Ошибка'
        };
        return statusMap[status] || status;
    }

    function saveQueueItem() {
        const tag = document.getElementById('queue-tag').value.trim();
        const title = document.getElementById('queue-title').value.trim();
        const filterStrategy = document.getElementById('queue-filter').value;
        const priority = parseInt(document.getElementById('queue-priority').value);

        if (!tag || !title) {
            showToast('Тег и название видео обязательны', 'warning');
            return;
        }

        fetch('/queue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                tag: tag,
                title: title,
                filter_strategy: filterStrategy,
                priority: priority
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(data.message, 'success');
                hideQueueForm();
                loadQueue();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка добавления в очередь', 'error');
            console.error('Ошибка:', error);
        });
    }

    function deleteQueueItem(itemId) {
        if (!confirm('Вы уверены, что хотите удалить этот элемент из очереди?')) {
            return;
        }

        fetch(`/queue/${itemId}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(data.message, 'success');
                loadQueue();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка удаления', 'error');
            console.error('Ошибка:', error);
        });
    }

    function clearQueue() {
        if (!confirm('Вы уверены, что хотите очистить всю очередь?')) {
            return;
        }

        fetch('/queue', {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                item_ids: Array.from(document.querySelectorAll('.queue-item')).map(item => item.dataset.id)
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.status === 'success') {
                showToast(data.message, 'success');
                loadQueue();
            } else {
                showToast(data.message, 'error');
            }
        })
        .catch(error => {
            showToast('Ошибка очистки очереди', 'error');
            console.error('Ошибка:', error);
        });
    }

    function updateQueueStats() {
        fetch('/queue/stats')
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    document.getElementById('total-queue-count').textContent = data.stats.total;
                    document.getElementById('processing-queue-count').textContent = data.stats.processing;
                    document.getElementById('completed-queue-count').textContent = data.stats.completed;
                }
            })
            .catch(error => {
                console.error('Ошибка обновления статистики очереди:', error);
            });
    }
});
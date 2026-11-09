'use strict';
(() => {
  const data = window.WORKFLOW_KIT;
  const dialog = document.getElementById('detail-dialog');
  const content = document.getElementById('dialog-content');
  const escape = value => String(value).replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const findSkill = id => data.skills.find(skill => skill.id === id);
  let lastTrigger;
  let timer;
  function notify(message) {
    const toast = document.getElementById('toast');
    clearTimeout(timer); toast.textContent = message; toast.hidden = false;
    timer = setTimeout(() => { toast.hidden = true; }, 3000);
  }
  async function copy(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text);
      else {
        const area = document.createElement('textarea'); area.value = text;
        area.style.position = 'fixed'; area.style.opacity = '0'; document.body.append(area);
        area.select(); const success = document.execCommand('copy'); area.remove();
        if (!success) throw new Error('clipboard unavailable');
      }
      notify('已复制，可以粘贴到终端或新聊天。');
    } catch {
      notify('浏览器未允许复制，请选中命令或提示词手动复制。');
    }
  }
  function show(type, html, trigger) {
    lastTrigger = trigger || document.activeElement;
    document.getElementById('dialog-type').textContent = type;
    content.innerHTML = '<div class="dialog-body">' + html + '</div>';
    if (!dialog.open) dialog.showModal();
    dialog.scrollTop = 0;
    document.getElementById('close-dialog').focus();
  }
  function openSkill(id, trigger) {
    const skill = findSkill(id); if (!skill) return;
    const download = 'downloads/' + skill.id + '-' + data.version + '.zip';
    show('技能详情 / ' + skill.group,
      '<h2 id="dialog-title">' + escape(skill.title) + '</h2><p class="intro">' + escape(skill.summary) + '</p>' +
      '<p class="caption">$' + escape(skill.id) + ' · ' + skill.files + ' 个文件 · v' + escape(data.version) + '</p>' +
      '<h3>试一个具体任务</h3><pre>' + escape(skill.prompt) + '</pre><p><strong>预期产物：</strong>' + escape(skill.expected) + '</p>' +
      '<div class="actions"><button type="button" class="button primary" data-copy-skill="' + skill.id + '">复制试用提示</button><a class="button secondary" href="' + download + '" download>下载这项技能</a></div>' +
      '<h3>适用范围</h3><p>' + escape(skill.description) + '</p><details><summary>阅读完整技能正文</summary><pre>' + escape(skill.body) + '</pre></details>' +
      '<p class="caption">这是可下载的指令与资源包。此页面不会启动模型、执行命令或修改你的项目。</p>', trigger);
  }
  function openCase(id, trigger) {
    const item = data.cases.find(item => item.id === id); if (!item) return;
    const list = values => '<ul>' + values.map(value => '<li>' + escape(value) + '</li>').join('') + '</ul>';
    const image = item.image ? '<figure><img src="' + item.image + '" alt="页间阅读盲盒的项目保留界面截图"><figcaption>' + escape(item.image_caption) + '</figcaption></figure>' : '';
    show('项目案例 / ' + item.name,
      '<p class="caption">' + escape(item.label) + ' · 历史记录 ' + item.date + '</p><h2 id="dialog-title">' + escape(item.title) + '</h2><p class="intro">' + escape(item.intro) + '</p>' + image +
      '<h3>遇到的问题</h3><p>' + escape(item.problem) + '</p><h3>关键判断与做法</h3>' + list(item.decisions) +
      '<h3>留下的实际产物</h3>' + list(item.outcomes) +
      '<dl class="facts">' + Object.entries(item.facts).map(([key,value]) => '<div><dt>' + escape(key) + '</dt><dd>' + escape(value) + '</dd></div>').join('') + '</dl>' +
      '<div class="boundary"><h3 style="margin-top:0">证据说明与未验证项</h3><p>' + escape(item.limits) + '</p></div>' +
      '<h3>沉淀成的方法</h3><p>' + escape(item.lesson) + '</p><div class="chips">' + item.skills.map(id => '<button type="button" data-skill="' + id + '">' + escape(findSkill(id).title) + '</button>').join('') + '</div>' +
      '<div class="actions"><a class="button secondary" href="evidence/' + item.id + '.html" target="_blank" rel="noopener">查看公开证据说明</a></div>', trigger);
  }
  document.addEventListener('click', event => {
    const trigger = event.target.closest('button, a'); if (!trigger) return;
    if (trigger.dataset.skill) openSkill(trigger.dataset.skill, trigger);
    if (trigger.dataset.case) openCase(trigger.dataset.case, trigger);
    if (trigger.dataset.copy !== undefined) copy(trigger.dataset.copy);
    if (trigger.dataset.copySkill) copy(findSkill(trigger.dataset.copySkill).prompt);
  });
  document.getElementById('close-dialog').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', event => { if (event.target === dialog) { const box=dialog.getBoundingClientRect(); if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom) dialog.close(); } });
  dialog.addEventListener('close', () => { if (lastTrigger && lastTrigger.isConnected) lastTrigger.focus(); });
  let category = 'all';
  function filter() {
    const query = document.getElementById('skill-search').value.normalize('NFKC').trim().toLocaleLowerCase();
    let visible = 0;
    for (const row of document.querySelectorAll('.skill-row')) {
      const skill = findSkill(row.dataset.id);
      const text = [skill.id,skill.title,skill.summary,skill.group,skill.description].join(' ').normalize('NFKC').toLocaleLowerCase();
      const matches = (category === 'all' || skill.group === category) && (!query || text.includes(query));
      row.hidden = !matches; if(matches) visible++;
    }
    document.getElementById('skill-count').textContent = visible + ' 项工作流';
    document.getElementById('empty-skills').hidden = visible !== 0;
  }
  document.getElementById('skill-search').addEventListener('input', filter);
  for (const button of document.querySelectorAll('[data-filter]')) button.addEventListener('click', () => {
    category = button.dataset.filter;
    document.querySelectorAll('[data-filter]').forEach(tab => tab.setAttribute('aria-pressed',String(tab===button)));
    filter();
  });
  const routes = {
    product: {question:'“我想做一个 AI 产品，先做什么？”',steps:[['收敛核心场景','requirements-shaping'],['寻找成熟基础','reuse-first'],['确定验证路径','delivery-acceptance']],link:'在页间项目中看这类判断',case:'between-pages'},
    takeover: {question:'“这里有几份源码和构建包，接着做哪份？”',steps:[['核对版本与入口','project-takeover'],['定位最有影响的风险','engineering-audit-remediation'],['建立可核对的交付证据','software-delivery-evidence']],link:'在 WeldSTA 项目中看这类判断',case:'weldsta'},
    delivery: {question:'“测试通过了，现在能交给用户了吗？”',steps:[['核对实际使用路径','delivery-acceptance'],['对应版本、材料与结果','software-delivery-evidence'],['把失败变成可验证的改进','failure-learning']],link:'在光赢大师项目中看验证边界',case:'guangying'}
  };
  for (const button of document.querySelectorAll('[data-route]')) button.addEventListener('click', () => {
    document.querySelectorAll('[data-route]').forEach(tab => tab.setAttribute('aria-pressed',String(tab===button)));
    const route=routes[button.dataset.route];
    document.getElementById('route-content').innerHTML='<p class="route-question">'+escape(route.question)+'</p><ol class="route-steps">'+route.steps.map(([title,id])=>'<li><span>'+escape(title)+'</span><small>'+escape(findSkill(id).title)+'</small></li>').join('')+'</ol><button type="button" class="text-link" data-case="'+route.case+'">'+escape(route.link)+'</button>';
  });
  const caseHash=window.location.hash.replace('#case-','');
  if(window.location.hash.startsWith('#case-') && data.cases.some(item=>item.id===caseHash)) openCase(caseHash);
})();

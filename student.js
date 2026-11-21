(function () {
  "use strict";

  const microcourses = new Map([
    ["S1", "等式两边各项同乘"],
    ["S2", "去括号时逐项分配符号"],
  ]);
  const correctionNotes = new Map([
    ["M1", "再想一想移项时，等式两边要同加或同减什么。"],
    ["M2", "再检查等号右边的常数项是否也乘了 6。"],
    ["M4", "再检查括号前的负系数有没有乘到括号里的每一项。"],
  ]);
  let workbookNumber = 0;

  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content != null) node.textContent = content;
    return node;
  }

  function button(className, label, action) {
    const node = element("button", className, label);
    node.type = "button";
    node.disabled = typeof action !== "function";
    if (!node.disabled) node.addEventListener("click", action);
    return node;
  }

  function list(value) {
    return Array.isArray(value) ? value : [];
  }

  function disclosure(className, title) {
    const details = element("details", className);
    details.append(element("summary", "", title));
    return details;
  }

  function numericAnswer(value) {
    if (value == null) return null;
    const text = String(value).normalize("NFKC").replace(/−/g, "-").trim()
      .replace(/^x\s*=\s*/i, "");
    const fraction = /^([+-]?\d+)\s*\/\s*([+-]?\d+)$/.exec(text);
    if (fraction) {
      const denominator = BigInt(fraction[2]);
      return denominator === 0n ? null : [BigInt(fraction[1]), denominator];
    }
    const decimal = /^([+-]?)(\d*)(?:\.(\d*))?$/.exec(text);
    if (!decimal || !(decimal[2] || decimal[3])) return null;
    const places = decimal[3] || "";
    return [BigInt(decimal[1] + (decimal[2] || "0") + places), 10n ** BigInt(places.length)];
  }

  function sameValue(a, b) {
    return Boolean(a && b && a[0] * b[1] === b[0] * a[1]);
  }

  function answerForm(id, labelText, submitText, expected, retryNote) {
    const form = element("form", "ys-answer-form");
    const label = element("label", "ys-answer-label", labelText);
    const controls = element("div", "ys-answer-controls");
    const input = element("textarea", "ys-answer-input");
    const submit = element("button", "ys-button ys-button--primary", submitText);
    const note = element("p", "ys-answer-note", "□ 本地规则核对 · 填整数、小数或分数，可按 Enter。");
    const feedback = element("p", "ys-feedback");
    const target = numericAnswer(expected);

    label.htmlFor = input.id = id;
    note.id = id + "-note";
    input.setAttribute("aria-describedby", note.id);
    input.rows = 1;
    input.maxLength = 80;
    input.autocapitalize = "off";
    input.autocomplete = "off";
    input.spellcheck = false;
    submit.type = "submit";
    feedback.setAttribute("role", "status");
    feedback.setAttribute("aria-atomic", "true");

    if (!target) {
      input.disabled = submit.disabled = true;
      note.textContent = "当前题目缺少本地核对规则。";
    }

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.isComposing && event.keyCode !== 229) {
        event.preventDefault();
        if (!event.repeat) form.requestSubmit();
      }
    });
    input.addEventListener("input", () => {
      feedback.textContent = "";
      feedback.removeAttribute("data-state");
      input.removeAttribute("aria-invalid");
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      if (!target) return;
      const answer = numericAnswer(input.value);
      const correct = sameValue(answer, target);
      feedback.dataset.state = correct ? "pass" : "retry";
      if (correct) {
        input.removeAttribute("aria-invalid");
        feedback.textContent = "核对通过。把结果代回原等式，再验算一遍。";
      } else if (!answer) {
        input.setAttribute("aria-invalid", "true");
        feedback.textContent = input.value.trim()
          ? "请输入一个有效的整数、小数或分数。"
          : "先写下你求出的 x 值。";
        input.focus();
      } else {
        input.removeAttribute("aria-invalid");
        feedback.textContent = retryNote(answer);
      }
    });

    controls.append(input, submit);
    form.append(label, controls, note, feedback);
    return form;
  }

  function fraction(numerator, denominator) {
    const node = element("span", "ys-fraction");
    node.append(element("span", "ys-numerator", numerator), element("span", "ys-denominator", denominator));
    return node;
  }

  function equation(className, spoken, ...parts) {
    const line = element("div", "ys-equation" + (className ? " " + className : ""));
    line.setAttribute("role", "math");
    line.setAttribute("aria-label", spoken);
    for (const part of parts) {
      const term = typeof part === "string" ? element("span", "", part) : part;
      term.setAttribute("aria-hidden", "true");
      line.append(term);
    }
    return line;
  }

  function exercise(item, wrongAnswers, id) {
    const section = element("article", "ys-exercise");
    const title = element("h2", "ys-section-title", "第 12 题 · 去分母");
    section.append(title);
    if (!item) {
      section.append(element("p", "ys-empty", "本地题库中没有第 12 题。"));
      return section;
    }

    const problem = element("div", "ys-problem");
    problem.append(
      element("p", "ys-kicker", "解方程 □"),
      equation("", "x 减一的差除以二，减去 x 加二的和除以三，等于一。",
        fraction("x − 1", "2"), "−", fraction("x + 2", "3"), "=", "1"),
    );

    const transform = element("details", "ys-transform");
    const toggle = element("summary", "ys-transform-toggle");
    toggle.append(
      element("span", "ys-expand-label", "两边同乘 6"),
      element("span", "ys-collapse-label", "收起同乘步骤"),
    );
    transform.append(
      toggle,
      element("p", "ys-transform-caption", "把等号两边的每一项都乘 6，右边的 1 也要乘。"),
      equation("ys-equation--expanded", "三乘以 x 减一的差，减去二乘以 x 加二的和，等于六。",
        "3(x − 1)", "−", "2(x + 2)", "=", "6"),
    );

    const form = answerForm(id + "-q12", "我的答案 · x 的值", "核对第 12 题", item.answer, (answer) => {
      const match = wrongAnswers.find(([known]) => sameValue(known, answer));
      const hint = match && correctionNotes.get(match[1]);
      return "还没对上。" + (hint || "试着把你的结果代回原等式，看看两边是否相等。");
    });
    section.append(problem, transform, form);
    return section;
  }

  function margin(student, response, openCockpit, openModel) {
    const aside = element("aside", "ys-margin");
    const current = element("div", "ys-current-student");
    current.append(
      element("h2", "ys-student-name", student.name),
      element("span", "ys-simulated", "□ 模拟作答"),
    );
    aside.append(current);

    if (response && response.response != null) {
      const work = element("p", "ys-demo-answer");
      work.append("第 12 题作答 ", element("strong", "", "x = " + response.response));
      aside.append(work);
    }
    const steps = list(student.wrong_steps);
    if (steps.length) {
      const details = disclosure("ys-disclosure", "展开原作答步骤");
      const ordered = element("ol", "ys-steps");
      for (const step of steps) ordered.append(element("li", "", step));
      details.append(ordered);
      aside.append(details);
    }

    if (student.id === "S1") {
      const action = typeof openCockpit === "function" ? () => openCockpit() : null;
      aside.append(
        button("ys-button ys-button--quiet", "查看协作教案", action),
        element("p", "ys-cache-note", "此份协作教案以小川为例。"),
      );
    } else {
      aside.append(element("p", "ys-cache-note", "此份协作教案以小川为例。"));
    }

    const helper = element("div", "ys-helper");
    const character = element("img", "ys-helper-image");
    character.src = "models/analyst.png";
    character.alt = "";
    character.decoding = "async";
    character.addEventListener("error", () => { character.hidden = true; });
    const copy = element("div", "ys-helper-copy");
    const action = typeof openModel === "function" ? () => openModel("analyst") : null;
    copy.append(
      element("strong", "", "学情分析师"),
      button("ys-link-button", "查看角色示意", action),
    );
    helper.append(character, copy);
    aside.append(helper);
    return aside;
  }

  function followup(student, id) {
    const section = element("div", "ys-followup");
    const transfer = element("section", "ys-transfer");
    transfer.append(element("h2", "ys-section-title", "迁移练习"));
    if (student.transfer?.q) {
      transfer.append(
        element("p", "ys-transfer-question", student.transfer.q),
        answerForm(id + "-transfer", "我的答案 · x 的值", "核对迁移题", student.transfer.a,
          () => "还没对上。回到这道题，检查等式两边的运算，再试一次。"),
      );
    } else {
      transfer.append(element("p", "ys-empty", "这位学生暂无本地迁移题。"));
    }

    const media = element("section", "ys-media");
    media.append(element("h2", "ys-section-title", "配套微课"));
    const name = microcourses.get(student.id);
    if (name) {
      const video = element("video", "ys-video");
      const file = "microcourse-" + student.id + ".mp4";
      const failure = element("p", "ys-empty", "本地视频暂时无法播放。");
      video.controls = true;
      video.playsInline = true;
      video.preload = "none";
      video.setAttribute("aria-label", name);
      video.append("当前浏览器不支持视频播放。");
      failure.hidden = true;
      failure.setAttribute("role", "status");
      video.addEventListener("error", () => { failure.hidden = false; });
      video.src = (window.location.protocol === "file:" ? "media/" : "/microcourses/") + file;
      media.append(element("p", "ys-media-status", "○ 本地已生成 · " + name), video, failure);
    } else if (student.id === "S3") {
      media.append(element("p", "ys-media-status", "第三段 · 待复核"));
    } else {
      media.append(element("p", "ys-empty", "这位学生暂无本地微课。"));
    }
    section.append(transfer, media);
    return section;
  }

  function sectionHeading(title, note) {
    const header = element("header", "ys-section-heading");
    header.append(element("h2", "ys-section-title", title), element("p", "ys-simulated", note));
    return header;
  }

  function knowledgeIndex(points, pointItems, responses, id) {
    const section = element("section", "ys-knowledge");
    section.append(sectionHeading("知识索引", `${points.length} 个知识点 · 展开查看先修关系`));
    const entries = new Map();
    const index = element("div", "ys-knowledge-list");
    for (const [position, point] of points.entries()) {
      const detail = element("details", "ys-knowledge-point");
      const heading = element("summary", "ys-point-heading");
      detail.id = `${id}-knowledge-${position + 1}`;
      heading.append(element("span", "ys-point-id", point.id), element("span", "ys-point-title", point.title));
      detail.append(heading);
      entries.set(point.id, { point, detail, heading });
      index.append(detail);
    }

    function pointLink(pointId) {
      const entry = entries.get(pointId);
      if (!entry) return element("span", "ys-point-id", pointId);
      const link = button("ys-point-link", pointId, () => {
        entry.detail.open = true;
        entry.heading.focus();
      });
      link.setAttribute("aria-label", `在知识索引中展开 ${pointId} ${entry.point.title}`);
      link.setAttribute("aria-controls", entry.detail.id);
      return link;
    }

    for (const { point, detail } of entries.values()) {
      const body = element("div", "ys-point-detail");
      const prerequisites = list(point.prerequisites);
      const line = element("div", "ys-point-related");
      line.append(element("span", "", prerequisites.length ? "先修知识" : "无先修要求"));
      for (const prior of prerequisites) line.append(pointLink(prior));
      const related = (pointItems.get(point.id) || []).filter((item) => responses.has(item.id));
      body.append(line);
      if (related.length) {
        const recorded = related.map((item) => {
          const answer = responses.get(item.id);
          const status = answer.correct === true ? "正确" : answer.correct === false ? "有误" : "未标记";
          return `${item.id} ${status}`;
        });
        body.append(element("p", "", "□ 对应作答 · " + recorded.join("、")));
      }
      detail.append(body);
    }
    section.append(index);
    return { section, pointLink };
  }

  function records(items, responses, pointLink) {
    const section = element("section", "ys-records");
    const answered = items.filter((item) => responses.has(item.id));
    const correct = answered.filter((item) => responses.get(item.id).correct === true).length;
    section.append(sectionHeading("逐题作答", `□ 模拟数据 · ${answered.length} 题有记录 · ${correct} 题正确`));
    const result = element("ul", "ys-record-list");
    for (const item of items) {
      const response = responses.get(item.id);
      const row = element("li", "ys-record");
      const content = element("div", "ys-record-content");
      const outcome = element("p", "ys-record-result");
      const links = element("div", "ys-record-kps");
      content.append(element("p", "ys-record-stem", item.stem));
      if (response && response.response != null) {
        const status = response.correct === true ? "正确" : response.correct === false ? "有误" : "未标记";
        if (typeof response.correct === "boolean") outcome.dataset.correct = String(response.correct);
        outcome.append(element("span", "", status), element("span", "", `作答 ${response.response}`));
      } else {
        outcome.textContent = "暂无作答";
      }
      content.append(outcome);
      for (const pointId of list(item.kp)) links.append(pointLink(pointId));
      row.append(element("span", "ys-record-id", item.id), content, links);
      result.append(row);
    }
    section.append(result);
    return section;
  }

  function render(host, { openCockpit, openModel } = {}) {
    const source = window.LESSON || {};
    const students = list(source.students);
    const items = list(source.items);
    const points = list(source.knowledge_points);
    const demo = items.find((item) => item.id === "Q12");
    const pointItems = new Map();
    for (const item of items) {
      for (const pointId of list(item.kp)) {
        if (!pointItems.has(pointId)) pointItems.set(pointId, []);
        pointItems.get(pointId).push(item);
      }
    }
    const seenErrors = new Map();
    for (const student of students) {
      const response = list(student.responses).find((item) => item.item === "Q12");
      if (response?.correct === false && response.misconception) {
        seenErrors.set(response.response, response.misconception);
      }
    }
    for (const [answer, code] of Object.entries(demo?.wrong_answer_map || {})) seenErrors.set(answer, code);
    const wrongAnswers = Array.from(seenErrors, ([value, code]) => [numericAnswer(value), code]);

    const id = `yincai-workbook-${++workbookNumber}`;
    const root = element("div", "yincai-student");
    root.lang = "zh-CN";
    const book = element("div", "ys-book");
    const intro = element("header", "ys-intro");
    intro.append(
      element("p", "ys-intro-note", "□ 模拟个案　/　一元一次方程"),
      element("h1", "ys-title", "演算手册"),
    );
    book.append(intro);
    root.append(book);

    if (students.length) {
      const index = element("nav", "ys-index");
      const page = element("section", "ys-student-page");
      const pages = new Map();
      let selected = -1;
      index.setAttribute("aria-label", "切换模拟学生");
      page.id = id + "-page";
      const tabs = students.map((student, position) => {
        const tab = button("ys-tab", "", () => selectStudent(position));
        tab.id = id + "-student-" + (position + 1);
        tab.setAttribute("aria-controls", page.id);
        tab.append(element("span", "ys-tab-code", student.id), element("span", "ys-tab-name", student.name));
        index.append(tab);
        return tab;
      });

      function selectStudent(position) {
        if (position === selected) return;
        const currentVideo = page.querySelector("video");
        if (currentVideo && !currentVideo.paused) currentVideo.pause();
        selected = position;
        for (const [tabPosition, tab] of tabs.entries()) {
          tab.setAttribute("aria-pressed", String(tabPosition === position));
        }
        page.setAttribute("aria-labelledby", tabs[position].id);
        if (!pages.has(position)) {
          const student = students[position];
          const studentId = `${id}-${position + 1}`;
          const responses = new Map(list(student.responses).map((response) => [response.item, response]));
          const knowledge = knowledgeIndex(points, pointItems, responses, studentId);
          const spread = element("div", "ys-spread");
          spread.append(exercise(demo, wrongAnswers, studentId), margin(student, responses.get("Q12"), openCockpit, openModel));
          pages.set(position, [
            spread,
            followup(student, studentId),
            records(items, responses, knowledge.pointLink),
            knowledge.section,
          ]);
        }
        page.replaceChildren(...pages.get(position));
      }

      index.addEventListener("keydown", (event) => {
        const current = tabs.indexOf(event.target);
        if (current < 0 || event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return;
        let next;
        if (event.key === "ArrowLeft") next = (current + tabs.length - 1) % tabs.length;
        else if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
        else if (event.key === "Home") next = 0;
        else if (event.key === "End") next = tabs.length - 1;
        else return;
        event.preventDefault();
        tabs[next].focus();
        selectStudent(next);
      });

      selectStudent(0);
      book.append(index, page);
    } else {
      book.append(element("p", "ys-empty", "暂未载入本地模拟学生。"));
    }

    const previousVideo = host.querySelector(".yincai-student .ys-video");
    if (previousVideo && !previousVideo.paused) previousVideo.pause();
    host.replaceChildren(root);
  }

  window.YincaiStudent = Object.freeze({ render });
}());

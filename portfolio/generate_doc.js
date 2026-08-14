const fs = require("fs");
const { Document, Packer, Paragraph, TextRun, Header, Footer, AlignmentType,
        LevelFormat, HeadingLevel, BorderStyle, PageNumber } = require("docx");

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Microsoft YaHei", size: 21 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, font: "Microsoft YaHei", color: "1a1d23" },
        paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 26, bold: true, font: "Microsoft YaHei", color: "2563eb" },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 22, bold: true, font: "Microsoft YaHei", color: "2d3038" },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ]
  },
  numbering: {
    config: [
      { reference: "bullets",
        levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1200, right: 1200, bottom: 1100, left: 1200 }
      }
    },
    headers: {
      default: new Header({ children: [
        new Paragraph({ alignment: AlignmentType.RIGHT, spacing: { after: 100 },
          children: [new TextRun({ text: "张逸帆 · AI 产品作品集", font: "Microsoft YaHei", size: 16, color: "999999" })] })
      ]})
    },
    footers: {
      default: new Footer({ children: [
        new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 100 },
          border: { top: { style: BorderStyle.SINGLE, size: 1, color: "cccccc", space: 4 } },
          children: [
            new TextRun({ text: "Page ", font: "Microsoft YaHei", size: 16, color: "999999" }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 16, color: "999999" }),
          ]})
      ]})
    },
    children: [
      // ── TITLE ──
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "AI 产品作品集", bold: true, size: 40, font: "Microsoft YaHei", color: "1a1d23" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 80 },
        children: [new TextRun({ text: "张逸帆 · 复旦大学", size: 22, font: "Microsoft YaHei", color: "666666" })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
        children: [
          new TextRun({ text: "腾讯 · 微信支付风控", size: 20, font: "Microsoft YaHei", color: "15803d" }),
          new TextRun({ text: "    ", size: 20 }),
          new TextRun({ text: "米哈游 · 原神国际化", size: 20, font: "Microsoft YaHei", color: "2563eb" }),
        ] }),
      new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 400 },
        children: [new TextRun({ text: "以下两个项目均在实习期间完成。Demo 版本已去除敏感业务信息，保留完整产品设计逻辑。", size: 18, font: "Microsoft YaHei", color: "888888", italics: true })] }),

      // ═══════════ PROJECT 1 ═══════════
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("项目一 · 虚拟用户访谈平台")] }),
      new Paragraph({ spacing: { after: 120 }, children: [
        new TextRun({ text: "米哈游 · 原神海外用户研究  |  纯前端单文件实现  |  离线可用", size: 18, font: "Microsoft YaHei", color: "888888" }),
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("解决什么问题")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "原神海外用户研究团队在规划版本内容时，需要提前了解不同区域玩家对新功能的接受度和流失原因。但传统访谈面临三个瓶颈：跨国招募玩家排期 2-4 周、单次访谈仅覆盖 3-5 人导致结论碎片化、不同研究员对同一批访谈记录的理解存在主观偏差。", size: 21, font: "Microsoft YaHei" }),
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("核心功能")] }),
      ...[
        "28 位虚拟玩家：基于真实玩家数据建模，每位包含 UID/付费金额/游戏时长/流失原因分析等 20+ 档案字段",
        "多维度筛选：国家/年龄/平台/付费等级/所属游戏，滑块+标签组合筛选",
        "单用户深度访谈：AI 基于用户档案生成回答，附带推理链路和信息源引用",
        "群聊推演：多用户同时回答，6 种人设类型差异化输出",
        "代表用户合成：行为标签频率加权聚合，生成群体典型画像",
      ].map(text =>
        new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 },
          children: [new TextRun({ text, size: 20, font: "Microsoft YaHei" })] })
      ),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("设计亮点")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "不同于通用 Chatbot——每条回答先检索用户档案数据作为依据，再进行角色化推演，而非自由发挥。回答上方有可展开的「本轮用户思考过程」面板，展示推理依据和原始信息源，让研究员能够判断回答的可信程度。纯前端单文件实现，离线可用，无需部署。", size: 21, font: "Microsoft YaHei" }),
      ]}),

      // ═══════════ PROJECT 2 ═══════════
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("项目二 · 地址信息审核 Agent")] }),
      new Paragraph({ spacing: { after: 120 }, children: [
        new TextRun({ text: "腾讯 · 微信支付 KYC 风控  |  Python + Streamlit  |  ReAct Agent 架构", size: 18, font: "Microsoft YaHei", color: "888888" }),
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("解决什么问题")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "微信支付在个人客户身份识别（KYC）环节，需要核验客户提交的居住或联系地址是否真实存在。传统做法是审核员逐条在地图和搜索引擎上交叉比对——一条地址平均耗时 3-5 分钟，批量审核数百条地址时效率极低，且不同审核员的判断标准不统一。", size: 21, font: "Microsoft YaHei" }),
      ]}),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("核心功能")] }),
      ...[
        "LLM 地址层级理解 + 完整度评分（1-7 级），信息不足时主动追问",
        "高德地图 geocode + Bing 搜索双源交叉验证",
        "5 条量化审核标准：完整度/可搜索性/定位准确/门牌号可查/特定地点豁免",
        "ReAct Agent 架构（Think → Act → Observe → Answer）",
        "预审报告环节：用户确认后才调用 API，避免无效调用",
        "Excel 批量处理 + 四列结构化审核报告（序号/地址/结论/依据+链接）",
      ].map(text =>
        new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 },
          children: [new TextRun({ text, size: 20, font: "Microsoft YaHei" })] })
      ),

      new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun("设计亮点")] }),
      new Paragraph({ spacing: { after: 100 }, children: [
        new TextRun({ text: "从提示词实验到 Agent 系统的完整迭代过程：初版提示词用万能公式起手，每轮用带人审标签的历史数据跑一轮，将 AI 结果与人审结果逐条对比——重点关注不一致 case 和「不确定」 case，归类原因后调整提示词。在基座模型间交叉验证，最终准确率从 80% 提升到约 95%，人力消耗降低约 1/3。方法论具有通用性，可扩展到商户资质审核、法律文书地址核验、企业注册信息验证等场景。", size: 21, font: "Microsoft YaHei" }),
      ]}),

      // ═══════════ COMMON ═══════════
      new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun("共同特点")] }),
      ...[
        "从真实业务问题出发，而非凭空造需求——原神用户研究和微信支付 KYC 均为实际业务场景",
        "完整的产品设计闭环：问题定义 → 标准制定 → 交互设计 → 落地验证",
        "注重 AI 输出的可信度和可追溯性：不是黑盒回答，而是展示推理过程和信息源，让用户能判断 AI 输出的质量",
      ].map(text =>
        new Paragraph({ numbering: { reference: "bullets", level: 0 }, spacing: { after: 60 },
          children: [new TextRun({ text, size: 20, font: "Microsoft YaHei" })] })
      ),

      // ── Footer note ──
      new Paragraph({ spacing: { before: 300 }, alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 1, color: "cccccc", space: 8 } },
        children: [new TextRun({ text: "Demo 版本已去除敏感业务信息，保留完整产品设计逻辑。", size: 18, font: "Microsoft YaHei", color: "999999", italics: true })] }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("AI产品作品集介绍.docx", buf);
  console.log("Done: " + (buf.length / 1024).toFixed(0) + " KB");
});

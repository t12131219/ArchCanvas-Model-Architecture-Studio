export type DraftParameterHelp = { label: string; description: string };

// Explanations of the registered authored-draft fields, not runtime observations.
const HELP: Readonly<Record<string, Readonly<Record<string, DraftParameterHelp>>>> = {
  Input: {
    shape: {
      label: '输入形状',
      description: '按顺序填写各维尺寸，例如 [1, 3, 32, 32] 表示批次 1、通道 3、高和宽各 32。可声明 1–8 维，各维为正整数；这是静态约定，不是运行测量。',
    },
    dtype: {
      label: '元素类型',
      description: '卷积、全连接和归一化需要 float32；Embedding 的索引需要 int64。float64 须与后续模块兼容。此处声明类型，不转换实际数据。',
    },
  },
  Linear: {
    in_features: {
      label: '输入特征数',
      description: '须等于上游张量的最后一维。例如输入 [1, 16] 时填 16；修改此值不会自动改变上游形状。',
    },
    out_features: {
      label: '输出特征数',
      description: '输出的最后一维变为此值，其他维度保留。例如 [1, 16] 可变为 [1, 32]；后续模块的输入参数也须匹配。',
    },
    bias: {
      label: '使用偏置',
      description: '开启后，每个输出特征都有一个可学习的加法偏置；关闭后只保留权重变换。此选项不改变输出形状。',
    },
  },
  GELU: {
    approximate: {
      label: '近似方式',
      description: 'none 使用 GELU 的原始计算形式，tanh 使用双曲正切近似。两者保留输入形状和浮点类型。',
    },
  },
  Dropout: {
    p: {
      label: '失活概率',
      description: '取 0–1。训练时以此概率把元素置零；p=0 不丢弃，p=1 全部置零，其他值会缩放保留元素。评估时直接传递输入，形状不变。',
    },
  },
  Flatten: {
    start_dim: {
      label: '展平起始维',
      description: '从此维开始合并轴，维度从 0 计数，负数从末尾计数。默认 1 保留第 0 维（常用作批次）；一维输入须改为 0。起始维须不晚于结束维，并落在输入维度范围内。',
    },
    end_dim: {
      label: '展平结束维',
      description: '合并到此维，包含该维；-1 表示最后一维。例如 [1, 3, 4] 从 1 到 -1 展平为 [1, 12]，元素类型保留。',
    },
  },
  Conv2d: {
    in_channels: {
      label: '输入通道数',
      description: '须等于 CHW 或 NCHW 输入的通道维；例如 [1, 3, 32, 32] 的通道数是 3。输入类型须为 float32。',
    },
    out_channels: {
      label: '输出通道数',
      description: '卷积产生的通道数。输出的通道维变为此值；高和宽由卷积核、步长、填充和膨胀共同决定。',
    },
    kernel_size: {
      label: '卷积核尺寸',
      description: '填写 [高, 宽] 两个正整数，例如 [3, 3]。卷积核决定每次采样的空间范围；设置过大可能使输出尺寸无效。',
    },
    stride: {
      label: '卷积步长',
      description: '填写 [高方向步长, 宽方向步长] 两个正整数。每次沿对应方向移动这么多格；增大步长通常会减小输出高和宽。',
    },
    padding: {
      label: '边缘填充',
      description: '填写 [高方向填充, 宽方向填充] 两个非负整数。每个方向的两侧各补对应数量的零；例如 [1, 1] 在四边各补一格。',
    },
    dilation: {
      label: '卷积核采样间距',
      description: '填写 [高方向间距, 宽方向间距] 两个正整数。1 表示连续采样，2 表示相邻采样点之间隔一格；增大会扩大有效卷积核范围。',
    },
    groups: {
      label: '通道分组数',
      description: '1 表示普通卷积；更大的值把输入和输出通道分为独立计算的组。分组数须同时整除输入通道数和输出通道数。',
    },
    bias: {
      label: '使用偏置',
      description: '开启后，每个输出通道都有一个可学习的加法偏置；关闭后只保留卷积权重。此选项不改变输出形状。',
    },
  },
  MaxPool2d: {
    kernel_size: {
      label: '池化窗口尺寸',
      description: '填写 [高, 宽] 两个正整数，例如 [2, 2]。每个窗口只保留最大值；输入须为 CHW 或 NCHW 浮点张量。',
    },
    stride: {
      label: '池化步长',
      description: '填写 [高方向步长, 宽方向步长] 两个正整数。每次沿对应方向移动这么多格；本目录默认 [2, 2]，可独立于窗口尺寸修改。',
    },
    padding: {
      label: '池化边缘填充',
      description: '填写 [高方向填充, 宽方向填充] 两个非负整数，两侧各补对应数量的位置。最大池化按负无穷处理这些位置；各值不得超过对应窗口尺寸的一半（向下取整）。',
    },
    dilation: {
      label: '窗口采样间距',
      description: '填写 [高方向间距, 宽方向间距] 两个正整数。1 表示连续采样，2 表示相邻采样点之间隔一格；增大会扩大有效窗口范围。',
    },
    ceil_mode: {
      label: '向上取整输出尺寸',
      description: '关闭时按向下取整计算输出高和宽；开启时允许末端的部分窗口，并按向上取整计算，再排除起点完全落入末端填充的窗口。',
    },
  },
  AdaptiveAvgPool2d: {
    output_size: {
      label: '目标空间尺寸',
      description: '填写 [输出高, 输出宽] 两个正整数，例如 [1, 1] 将每个通道归并为一个平均值。CHW 或 NCHW 的通道和批次维保留。',
    },
  },
  BatchNorm2d: {
    num_features: {
      label: '通道数',
      description: '须等于 float32 输入 [批次, 通道, 高, 宽] 的通道数。输入必须为 4 维，且每个通道的批次×高×宽至少为 2，以满足训练兼容检查。',
    },
    eps: {
      label: '数值稳定项',
      description: '归一化时加在方差上的小正数，用于避免除数为零。可填 1e-12–1，默认 1e-5；不改变张量形状。',
    },
    momentum: {
      label: '统计更新权重',
      description: '取 0–1，控制当前批次统计在运行均值和方差更新中的权重；例如 0.1 表示旧统计占 0.9、新统计占 0.1。仅在跟踪统计时使用，与优化器动量无关。',
    },
    affine: {
      label: '学习通道缩放与偏移',
      description: '开启后，每个通道具有可学习的缩放和偏移参数；关闭后只做归一化。输出形状保留。',
    },
    track_running_stats: {
      label: '跟踪运行统计',
      description: '开启后，训练时更新运行均值和方差，评估时使用这些统计；关闭后，训练和评估都使用当前批次的统计。',
    },
  },
  LayerNorm: {
    normalized_shape: {
      label: '归一化末尾形状',
      description: '须与 float32 输入的末尾若干维完全相同。例如 [2, 3, 16] 可填 [16] 或 [3, 16]；这些维一起归一化，输出形状保留。',
    },
    eps: {
      label: '数值稳定项',
      description: '归一化时加在方差上的小正数，用于避免除数为零。可填 1e-12–1，默认 1e-5；不改变张量形状。',
    },
    elementwise_affine: {
      label: '学习逐元素缩放与偏移',
      description: '开启后，归一化形状中的每个位置具有可学习的缩放和偏移参数；关闭后只做归一化。训练和评估均使用当前输入的统计。',
    },
  },
  Embedding: {
    num_embeddings: {
      label: '词表大小',
      description: '可查找的向量数量；int64 输入的实际索引须在 0 到此值减 1 之间。静态形状检查不能证明实际索引合法。',
    },
    embedding_dim: {
      label: '嵌入向量长度',
      description: '每个索引对应的 float32 向量长度。输出在输入形状末尾增加此维，例如 [1, 8] 配合 16 得到 [1, 8, 16]。',
    },
  },
  Concat: {
    dim: {
      label: '拼接维度',
      description: '沿此维拼接 a、b 两路输入，当前模块固定为两个输入。维度从 0 计数，-1 表示最后一维；两路的类型、维数和其他轴尺寸须相同，此轴尺寸相加。',
    },
  },
};

export function draftParameterHelp(kind: string, name: string): DraftParameterHelp | null {
  if (!Object.prototype.hasOwnProperty.call(HELP, kind)) return null;
  const fields = HELP[kind];
  if (!Object.prototype.hasOwnProperty.call(fields, name)) return null;
  return { ...fields[name] };
}

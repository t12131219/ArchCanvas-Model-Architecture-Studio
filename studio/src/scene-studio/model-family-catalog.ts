import type { NodeDetailKind } from "./types";

export interface ModelFamilyCatalogEntry {
  kind: NodeDetailKind;
  domain: string;
  aliases: readonly string[];
  differenceAxes: readonly string[];
}

// Names are lookup aliases, not claims that every variant executes an identical graph.
// differenceAxes records the evidence that a future IR adapter must inspect before choosing a precise view.
export const MODEL_FAMILY_CATALOG: readonly ModelFamilyCatalogEntry[] = [
  {
    kind: "linear-model",
    domain: "传统机器学习 / 线性与判别",
    aliases: [
      "Linear Regression", "Ridge", "Lasso", "Elastic Net", "Polynomial Regression", "Bayesian Linear Regression",
      "Logistic Regression", "Softmax Regression", "GLM", "GAM", "Quantile Regression", "Robust Regression",
      "Poisson Regression", "Negative Binomial Regression", "Tobit", "Perceptron", "LDA", "QDA",
      "Naive Bayes", "Gaussian Naive Bayes", "Multinomial Naive Bayes", "Bernoulli Naive Bayes",
      "Complement Naive Bayes", "Maximum Entropy", "CRF", "Structured SVM",
    ],
    differenceAxes: ["link function", "regularizer", "class likelihood", "linear versus quadratic score", "structured output"],
  },
  {
    kind: "kernel-machine",
    domain: "传统机器学习 / 核与邻域",
    aliases: [
      "SVM", "Linear SVM", "Kernel SVM", "SVR", "One-Class SVM", "Kernel Ridge Regression", "RBF Kernel",
      "Polynomial Kernel", "Sigmoid Kernel", "Laplacian Kernel", "Nystrom", "Random Fourier Features", "KNN",
      "Radius Neighbors", "Nearest Centroid", "KDE", "Local Outlier Factor", "Deep SVDD",
    ],
    differenceAxes: ["explicit versus implicit feature map", "support-vector versus neighbor aggregation", "classification versus regression"],
  },
  {
    kind: "decision-tree",
    domain: "传统机器学习 / 树",
    aliases: ["Decision Tree", "ID3", "C4.5", "C5.0", "CART", "Regression Tree", "Isolation Forest", "RuleFit"],
    differenceAxes: ["split criterion", "categorical handling", "leaf prediction", "isolation path"],
  },
  {
    kind: "ensemble",
    domain: "传统机器学习 / 集成",
    aliases: [
      "Random Forest", "Extra Trees", "GBDT", "AdaBoost", "XGBoost", "LightGBM", "CatBoost",
      "HistGradientBoosting", "NGBoost", "Bagging", "Boosting", "Voting", "Stacking", "Blending",
      "Random Subspace", "Rank Averaging", "Snapshot Ensemble", "Dynamic Ensemble Selection",
    ],
    differenceAxes: ["parallel bagging versus sequential boosting", "vote versus learned meta-model", "tree growth strategy"],
  },
  {
    kind: "clustering",
    domain: "传统机器学习 / 聚类与混合模型",
    aliases: [
      "K-Means", "Mini-Batch K-Means", "K-Medoids", "Hierarchical Clustering", "Agglomerative Clustering",
      "Divisive Clustering", "DBSCAN", "HDBSCAN", "OPTICS", "BIRCH", "Mean Shift", "Spectral Clustering",
      "Affinity Propagation", "Fuzzy C-Means", "GMM", "Variational GMM", "Graph Clustering", "Community Detection",
    ],
    differenceAxes: ["centroid versus density versus graph objective", "hard versus soft assignment", "iterative update rule"],
  },
  {
    kind: "decomposition",
    domain: "传统机器学习 / 降维与分解",
    aliases: [
      "PCA", "Kernel PCA", "Sparse PCA", "Incremental PCA", "SVD", "Truncated SVD", "LSA", "ICA", "NMF",
      "Factor Analysis", "Dictionary Learning", "Sparse Coding", "Random Projection", "LDA Topic Model", "PLS", "CCA",
      "MDS", "Isomap", "LLE", "Laplacian Eigenmaps", "Spectral Embedding", "t-SNE", "UMAP", "PHATE",
    ],
    differenceAxes: ["linear versus manifold embedding", "orthogonal/non-negative/sparse constraints", "parametric transform availability"],
  },
  {
    kind: "mlp",
    domain: "深度学习 / 前馈与激活",
    aliases: [
      "Linear", "MLP", "Sigmoid", "Tanh", "ReLU", "Leaky ReLU", "PReLU", "ELU", "SELU", "GELU", "SiLU",
      "Swish", "Mish", "Softplus", "Softsign", "Hard-Swish", "Hard-Sigmoid", "GLU", "GEGLU", "SwiGLU", "ReGLU",
      "Wide & Deep", "DeepFM", "xDeepFM", "Deep & Cross Network",
    ],
    differenceAxes: ["activation", "hidden expansion", "single versus gated branch", "feature-cross branch"],
  },
  {
    kind: "normalization",
    domain: "深度学习 / 归一化",
    aliases: [
      "Batch Normalization", "Layer Normalization", "Instance Normalization", "Group Normalization", "Local Response Normalization",
      "Weight Normalization", "Spectral Normalization", "RMSNorm", "ScaleNorm", "Adaptive LayerNorm", "QK-Norm",
    ],
    differenceAxes: ["reduction axes", "mean subtraction", "learned affine parameters", "data-dependent conditioning"],
  },
  {
    kind: "residual-block",
    domain: "视觉与通用连接",
    aliases: [
      "Residual Connection", "Skip Connection", "Highway Network", "Gated Connection", "ResNet", "ResNet-18", "ResNet-34",
      "ResNet-50", "ResNet-101", "ResNet-152", "Pre-Activation ResNet", "ResNeXt", "Wide ResNet", "SENet", "SKNet",
      "RegNet", "ConvNeXt", "RepVGG",
    ],
    differenceAxes: ["pre/post activation", "identity versus projection shortcut", "basic versus bottleneck block", "grouped convolution"],
  },
  {
    kind: "dense-connection",
    domain: "视觉与通用连接",
    aliases: ["Dense Connection", "DenseNet", "Cross-Stage Partial Connection", "Feature Pyramid", "Lateral Connection", "CSPNet"],
    differenceAxes: ["concat versus add", "all-layer versus partial-stage reuse", "multi-scale lateral connection"],
  },
  {
    kind: "inception",
    domain: "计算机视觉 / 多分支卷积",
    aliases: [
      "GoogLeNet", "Inception v1", "Inception v2", "Inception v3", "Inception v4", "Inception-ResNet",
      "Network in Network", "MaxViT", "CoAtNet",
    ],
    differenceAxes: ["branch kernel factorization", "pooling branch", "residual merge", "convolution-attention hybrid"],
  },
  {
    kind: "depthwise-convolution",
    domain: "计算机视觉 / 轻量卷积",
    aliases: [
      "Depthwise Separable Convolution", "Grouped Convolution", "Pointwise Convolution", "Xception", "MobileNet v1",
      "MobileNet v2", "MobileNet v3", "ShuffleNet", "ShuffleNet v2", "GhostNet", "EfficientNet", "EfficientNetV2",
      "MnasNet", "FBNet", "TinyNet", "PP-LCNet", "FasterNet", "SqueezeNet",
    ],
    differenceAxes: ["inverted residual", "channel shuffle", "squeeze-excitation", "expansion ratio", "activation"],
  },
  {
    kind: "unet",
    domain: "计算机视觉 / 分割与密集预测",
    aliases: [
      "U-Net", "U-Net++", "U-Net 3+", "Attention U-Net", "UNetFormer", "SegNet", "FCN", "PSPNet", "DeepLab",
      "DeepLabV2", "DeepLabV3", "DeepLabV3+", "HRNet", "RefineNet", "ICNet", "BiSeNet", "Mask2Former",
      "MaskFormer", "PointRend", "Panoptic FPN", "SAM", "MobileSAM", "FastSAM",
    ],
    differenceAxes: ["skip merge", "pyramid/context module", "query-based mask head", "prompt encoder"],
  },
  {
    kind: "vision-transformer",
    domain: "计算机视觉 / 视觉 Transformer 与检测",
    aliases: [
      "ViT", "DeiT", "Swin Transformer", "Swin V2", "PVT", "PVTv2", "Focal Transformer", "MViT", "MViTv2",
      "CvT", "LeViT", "MobileViT", "EfficientFormer", "BEiT", "BEiT v2", "MAE", "DINO", "DINOv2", "iBOT",
      "EVA", "Hiera", "DETR", "Deformable DETR", "DAB-DETR", "DN-DETR", "RT-DETR", "Sparse R-CNN",
      "TimeSformer", "VideoMAE", "Audio Spectrogram Transformer",
    ],
    differenceAxes: ["patch/token hierarchy", "global versus window attention", "classification versus object queries", "pretraining objective"],
  },
  {
    kind: "convolution",
    domain: "计算机视觉 / 卷积骨干与密集头",
    aliases: [
      "LeNet", "AlexNet", "ZFNet", "VGG", "VGG16", "VGG19", "R-CNN", "Fast R-CNN", "Faster R-CNN", "Mask R-CNN",
      "Cascade R-CNN", "SPP-Net", "SSD", "RetinaNet", "YOLO", "YOLOv2", "YOLOv3", "YOLOv4", "YOLOv5",
      "YOLOv6", "YOLOv7", "YOLOv8", "YOLOv9", "YOLOv10", "YOLOX", "FCOS", "ATSS", "CenterNet", "CornerNet",
      "PointNet", "PointNet++", "DGCNN", "VoxelNet", "PointPillars", "SECOND", "PV-RCNN", "RAFT", "PWC-Net", "FlowNet",
    ],
    differenceAxes: ["backbone", "proposal versus dense/query head", "feature pyramid", "post-processing", "2D versus 3D operator"],
  },
  {
    kind: "gru",
    domain: "序列模型 / 门控循环",
    aliases: ["GRU", "BiGRU", "SRU", "QRNN", "IndRNN"],
    differenceAxes: ["gate equations", "bidirectionality", "parallel recurrence approximation"],
  },
  {
    kind: "recurrent",
    domain: "序列模型 / LSTM 与记忆",
    aliases: ["Vanilla RNN", "Elman RNN", "Jordan RNN", "LSTM", "BiLSTM", "Deep RNN", "Residual RNN", "Peephole LSTM", "ConvLSTM", "ESN", "Echo State Network"],
    differenceAxes: ["cell state", "gate set", "convolutional transition", "reservoir versus trained recurrence"],
  },
  {
    kind: "bidirectional-recurrent",
    domain: "序列模型 / 双向编码",
    aliases: ["Bidirectional RNN", "BiLSTM", "BiGRU", "ELMo", "wav2vec", "wav2vec 2.0", "HuBERT", "WavLM"],
    differenceAxes: ["forward/backward merge", "recurrent versus Transformer encoder", "pretraining objective"],
  },
  {
    kind: "seq2seq",
    domain: "序列、NLP 与语音",
    aliases: [
      "Seq2Seq", "Encoder-Decoder", "Teacher Forcing", "Beam Search", "CTC", "Pointer Network", "Copy Network", "T5", "mT5",
      "FLAN-T5", "BART", "PEGASUS", "Whisper", "DeepSpeech", "Conformer", "Tacotron", "Tacotron 2", "FastSpeech",
      "FastSpeech 2", "Glow-TTS", "VITS",
    ],
    differenceAxes: ["attention/cross-attention", "autoregressive versus parallel decoding", "CTC versus decoder likelihood", "acoustic/vocoder boundary"],
  },
  {
    kind: "attention",
    domain: "注意力与 Transformer",
    aliases: [
      "Attention", "Additive Attention", "Dot-Product Attention", "Scaled Dot-Product Attention", "Self-Attention", "Cross-Attention",
      "Multi-Head Attention", "Multi-Query Attention", "Grouped-Query Attention", "Sparse Attention", "Local Attention",
      "Global Attention", "Causal Attention", "Sliding-Window Attention", "Linear Attention", "Performer Attention", "FlashAttention",
      "Deformable Attention", "Axial Attention", "Window Attention", "Channel Attention", "Spatial Attention", "Temporal Attention",
      "Talking-Heads Attention", "Multi-Head Latent Attention", "Transformer", "BERT", "RoBERTa", "ALBERT", "DistilBERT",
      "DeBERTa", "ELECTRA", "XLNet", "GPT", "GPT-2", "GPT-3", "GPT-4", "LLaMA", "LLaMA 2", "LLaMA 3",
      "Mistral", "Qwen", "Qwen2", "Gemma", "Falcon", "MPT", "BLOOM", "OPT", "Pythia", "Phi", "GLM", "ChatGLM",
      "Baichuan", "InternLM", "DeepSeek", "Yi", "Command R",
    ],
    differenceAxes: ["Q/K/V sharing", "mask and receptive field", "exact versus approximate attention", "encoder/decoder topology"],
  },
  {
    kind: "state-space",
    domain: "序列模型 / 状态空间与长卷积",
    aliases: ["Mamba", "Mamba-2", "S4", "RWKV", "RetNet", "Hyena", "Temporal Convolutional Network", "WaveNet", "Neural ODE", "Neural CDE"],
    differenceAxes: ["selective scan", "recurrent/parallel form", "long convolution", "continuous-time dynamics"],
  },
  {
    kind: "autoencoder",
    domain: "生成模型 / 自编码器",
    aliases: [
      "Autoencoder", "Undercomplete AE", "Denoising AE", "Sparse AE", "Contractive AE", "Stacked AE", "Convolutional AE",
      "Recurrent AE", "VQ-VAE", "VQ-VAE-2", "VQGAN", "Masked Autoencoder", "Autoencoder Anomaly Detection",
    ],
    differenceAxes: ["continuous versus discrete bottleneck", "reconstruction corruption", "perceptual/adversarial decoder loss"],
  },
  {
    kind: "variational-autoencoder",
    domain: "生成模型 / 变分潜变量",
    aliases: ["VAE", "β-VAE", "Conditional VAE", "Adversarial Autoencoder", "WAE", "InfoVAE", "NVAE", "RAE", "VGAE", "Graph Autoencoder"],
    differenceAxes: ["prior/posterior family", "conditioning", "regularizer divergence", "continuous versus graph decoder"],
  },
  {
    kind: "gan",
    domain: "生成模型 / 对抗学习",
    aliases: [
      "GAN", "DCGAN", "Conditional GAN", "AC-GAN", "InfoGAN", "WGAN", "WGAN-GP", "LSGAN", "SAGAN", "BigGAN",
      "StyleGAN", "StyleGAN2", "StyleGAN3", "Progressive GAN", "Pix2Pix", "Pix2PixHD", "CycleGAN", "StarGAN", "GauGAN",
      "SPADE", "SRGAN", "ESRGAN", "DeblurGAN", "DiscoGAN", "UNIT", "MUNIT", "UGATIT", "HiFi-GAN", "MelGAN",
    ],
    differenceAxes: ["adversarial objective", "conditional input", "paired/unpaired translation", "generator/discriminator backbone"],
  },
  {
    kind: "diffusion",
    domain: "生成模型 / 扩散与流匹配",
    aliases: [
      "DDPM", "DDIM", "Score Matching", "Score SDE", "NCSN", "LDM", "Latent Diffusion", "Stable Diffusion",
      "Stable Diffusion XL", "ControlNet", "T2I-Adapter", "GLIDE", "Imagen", "DALL-E", "DALL-E 2", "DALL-E 3", "DiT",
      "ADM", "EDM", "Consistency Model", "LCM", "AnimateDiff", "Video Diffusion", "Sora-like", "SR3", "Palette",
      "Flow Matching", "Rectified Flow", "Diffuser", "Diffusion Policy",
    ],
    differenceAxes: ["pixel versus latent space", "noise/velocity/data prediction", "sampler/scheduler", "conditioning branch", "U-Net versus DiT"],
  },
  {
    kind: "normalizing-flow",
    domain: "生成模型 / 可逆流",
    aliases: ["Normalizing Flow", "NICE", "RealNVP", "Glow", "MAF", "IAF", "FFJORD", "Neural Spline Flow", "Continuous Normalizing Flow", "WaveGlow"],
    differenceAxes: ["coupling/autoregressive/ODE transform", "inverse direction cost", "Jacobian determinant"],
  },
  {
    kind: "graph-message-passing",
    domain: "图神经网络与推荐",
    aliases: [
      "GCN", "GraphSAGE", "GAT", "GATv2", "GIN", "ChebNet", "Graph Transformer", "Graphormer", "GraphGPS", "MPNN",
      "GGNN", "R-GCN", "HAN", "HGT", "GTN", "DGI", "DeepWalk", "Node2Vec", "LINE", "SDNE", "ST-GCN",
      "Temporal GCN", "DCRNN", "T-GCN", "DySAT", "Graph WaveNet", "LightGCN", "NGCF", "User-CF", "Item-CF",
    ],
    differenceAxes: ["message function", "sum/mean/max/attention aggregation", "edge types", "temporal transition", "collaborative graph"],
  },
  {
    kind: "time-series-forecast",
    domain: "时间序列",
    aliases: [
      "AR", "MA", "ARMA", "ARIMA", "SARIMA", "VAR", "VARMA", "Exponential Smoothing", "Holt-Winters", "Prophet",
      "Kalman Filter", "DeepAR", "DeepState", "LSTNet", "N-BEATS", "N-HiTS", "TFT", "Informer", "Autoformer",
      "FEDformer", "Reformer", "ETSformer", "PatchTST", "TimesNet", "TiDE", "DLinear", "NLinear", "TSMixer",
      "iTransformer", "TimeMixer", "Crossformer", "SCINet", "Pyraformer", "MICN",
    ],
    differenceAxes: ["explicit decomposition", "autoregressive state", "covariates", "frequency/patch/mixer/attention backbone"],
  },
  {
    kind: "dual-encoder",
    domain: "多模态与检索推荐",
    aliases: [
      "CLIP", "ALIGN", "CLAP", "ImageBind", "DSSM", "Sentence-BERT", "SimCSE", "Contriever", "ColBERT", "Two-Tower",
      "YouTube DNN", "CLIP4Clip", "VideoCLIP", "Siamese Network", "SiamFC", "SiamRPN", "SiamMask", "SuperPoint", "SuperGlue", "LoFTR",
    ],
    differenceAxes: ["modality encoders", "late versus token-level interaction", "contrastive/ranking loss", "shared versus independent weights"],
  },
  {
    kind: "dqn",
    domain: "强化学习 / 值函数",
    aliases: [
      "Q-Learning", "Double Q-Learning", "DQN", "Double DQN", "Dueling DQN", "Prioritized Experience Replay", "NoisyNet",
      "Distributional DQN", "C51", "QR-DQN", "IQN", "FQF", "Rainbow", "DRQN", "Bootstrapped DQN", "Ape-X", "R2D2",
      "Agent57", "Munchausen DQN", "REM", "SARSA", "Expected SARSA", "Dyna-Q", "Value Iteration", "Policy Iteration",
    ],
    differenceAxes: ["on/off policy target", "distributional head", "replay prioritization", "target/online networks", "tabular versus neural"],
  },
  {
    kind: "actor-critic",
    domain: "强化学习 / 策略与模型",
    aliases: [
      "REINFORCE", "Policy Gradient", "Actor-Critic", "A2C", "A3C", "ACKTR", "ACER", "TRPO", "PPO", "IMPALA", "V-trace",
      "DPPO", "APPO", "RPO", "GRPO", "DDPG", "TD3", "SAC", "Soft Q-Learning", "MPO", "REDQ", "TQC", "DrQ",
      "Dreamer", "DreamerV2", "DreamerV3", "MuZero", "AlphaZero", "MCTS", "Decision Transformer", "Behavior Cloning",
      "GAIL", "CQL", "IQL", "AWAC", "MAPPO", "MADDPG", "QMIX", "RLHF", "PPO-RLHF", "DPO", "RLAIF",
    ],
    differenceAxes: ["policy/value/world-model components", "on/off policy", "discrete/continuous action", "trust-region or entropy objective", "single/multi-agent"],
  },
  {
    kind: "distillation",
    domain: "训练与压缩",
    aliases: ["Knowledge Distillation", "Feature Distillation", "Teacher-Student", "Pseudo Label", "Self-Training", "DistilBERT", "TinyNet"],
    differenceAxes: ["logit versus feature target", "temperature", "hard-label mixing", "online versus frozen teacher"],
  },
  {
    kind: "adapter-lora",
    domain: "参数高效适配与部署",
    aliases: [
      "LoRA", "QLoRA", "AdaLoRA", "DoRA", "Prefix Tuning", "Prompt Tuning", "P-Tuning", "Adapter", "BitFit",
      "Low-Rank Factorization", "Pruning", "Structured Pruning", "Unstructured Pruning", "Magnitude Pruning", "Lottery Ticket",
      "Quantization-Aware Training", "Post-Training Quantization", "GPTQ", "AWQ", "SmoothQuant",
    ],
    differenceAxes: ["additive low-rank versus serial adapter versus prompt parameters", "training versus post-training transform", "structured sparsity/quantization granularity"],
  },
];

export const NON_ARCHITECTURE_CONCEPTS = {
  learningParadigms: ["supervised", "unsupervised", "self-supervised", "federated", "continual", "online", "meta-learning", "AutoML", "NAS"],
  optimizersAndSchedules: ["SGD", "Adam", "AdamW", "AdaFactor", "LAMB", "Lion", "cosine annealing", "warmup", "one-cycle"],
  losses: ["MSE", "cross-entropy", "focal", "Dice", "IoU", "triplet", "InfoNCE", "KL", "CTC", "policy/value/entropy loss"],
  runtimesAndParallelism: ["TensorRT", "ONNX", "TVM", "TorchScript", "XLA", "tensor/pipeline/data parallelism", "ZeRO", "FSDP"],
} as const;


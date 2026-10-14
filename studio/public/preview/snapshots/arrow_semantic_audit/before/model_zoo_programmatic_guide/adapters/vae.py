"""Reviewed MNIST fully connected VAE adapter; upstream code is never imported."""
from spec import chain, op, parallel, ref


SOURCE = "deeplearning-models/pytorch_ipynb/autoencoder/ae-var.py"


def build():
    init = ref(SOURCE, "VariationalAutoencoder.__init__")
    enc = ref(SOURCE, "VariationalAutoencoder.encoder")
    dec = ref(SOURCE, "VariationalAutoencoder.decoder")
    sample = ref(SOURCE, "VariationalAutoencoder.reparameterize")
    forward = ref(SOURCE, "VariationalAutoencoder.forward")

    posterior = parallel("vae.posterior", "Posterior parameter heads", [
        chain("vae.mean_head", "Mean head", [
            op("vae.mu", "Linear 500 -> 15", "linear", [init, enc],
               "mu: [B,15]", ["self.z_mean; no activation"], parameter="z_mean"),
        ], [init, enc], "mu: [B,15]", expand=2,
           parameter_scope="z_mean"),
        chain("vae.logvar_head", "Log-variance head", [
            op("vae.logvar", "Linear 500 -> 15", "linear", [init, enc],
               "logvar: [B,15]", ["self.z_log_var; unbounded log variance"],
               parameter="z_log_var"),
        ], [init, enc], "logvar: [B,15]", expand=2,
           parameter_scope="z_log_var"),
    ], enc, "(mu, logvar)",
       ["same hidden input; independent Linear weights", "parallel means two tensor results, not addition"],
       expand=2)

    sampling = chain("vae.sampling", "Reparameterization", [
        parallel("vae.sample_operands", "Mean / scaled noise", [
            op("vae.mean_operand", "Retain mu", "tensor", sample,
               "[B,15]", ["mu is used unchanged"], input_selector="z_mu"),
            chain("vae.scaled_noise", "Standard deviation times noise", [
                op("vae.half_logvar", "Divide logvar by 2", "tensor", sample,
                   "[B,15]", ["z_log_var / 2."], input_selector="z_log_var"),
                op("vae.std", "Exponential", "activation", sample,
                   "std: [B,15]", ["exp(logvar/2), not exp(logvar)"],
                   expression="torch.exp(z_log_var / 2.)"),
                op("vae.noise_product", "std times epsilon", "mixing", sample,
                   "[B,15]", ["elementwise; epsilon enters through a side port"]),
            ], sample, "[B,15]", expand=2, input_selector="z_log_var"),
        ], sample, "(mu, std*epsilon)", expand=2, dispatch=True),
        op("vae.z", "Add mu + std*epsilon", "mixing", sample,
           "z: [B,15]", ["elementwise addition"],
           expression="z_mu + eps * torch.exp(z_log_var/2.)"),
    ], sample, "z: [B,15]", ["sampling also happens in eval mode in this source"], expand=2)

    encoder = chain("vae.encoder", "Encoder", [
        op("vae.enc_linear", "Linear 784 -> 500", "linear", [init, enc],
           "[B,500]", ["self.hidden_1"], parameter="hidden_1"),
        op("vae.enc_activation", "LeakyReLU", "activation", enc,
           "[B,500]", ["negative_slope=0.0001"], negative_slope=0.0001),
        posterior,
        sampling,
        op("vae.encoder_return", "Return (mu, logvar, z)", "tensor", enc,
           "three [B,15] tensors", ["tuple fields are retained; no concatenation"],
           output_tuple=["mu", "logvar", "z"]),
    ], [init, enc], "(mu, logvar, z)", expand=2,
       parameter_scope="hidden_1 / z_mean / z_log_var")

    decoder = chain("vae.decoder", "Decoder", [
        op("vae.dec_linear1", "Linear 15 -> 500", "linear", [init, dec],
           "[B,500]", ["self.linear_3"], parameter="linear_3"),
        op("vae.dec_activation", "LeakyReLU", "activation", dec,
           "[B,500]", ["negative_slope=0.0001"], negative_slope=0.0001),
        op("vae.dec_linear2", "Linear 500 -> 784", "linear", [init, dec],
           "[B,784]", ["self.linear_4"], parameter="linear_4"),
        op("vae.dec_sigmoid", "Sigmoid", "activation", dec,
           "decoded: [B,784]", ["pixel probabilities in [0,1]"],
           expression="torch.sigmoid(x)"),
    ], [init, dec], "decoded: [B,784]", expand=2,
       parameter_scope="linear_3 / linear_4")

    model_forward = chain("vae.forward", "Model forward", [
        encoder,
        op("vae.select_z", "Select encoded z", "tensor", forward,
           "[B,15]", ["decoder receives encoded, not mu or concatenated statistics"],
           input_selector="encoded"),
        decoder,
        op("vae.return", "Return (mu, logvar, z, decoded)", "tensor", forward,
           "[B,15] x 3; [B,784]",
           ["actual four-tensor forward result", "decoder output is one tuple field"],
           output_tuple=["mu", "logvar", "encoded", "decoded"]),
    ], forward, "four-tensor tuple", expand=1)

    tree = chain("vae.root", "MNIST fully connected VAE", [
        op("vae.input", "Flattened MNIST features", "input", forward,
           "[B,784]", ["caller reshapes [B,1,28,28] to [B,784] before model(features)",
                       "pixel range [0,1] from dataset ToTensor"],
           caller_preparation="features.view(-1, 28*28)"),
        model_forward,
    ], forward, "(mu, logvar, z, decoded)", expand=0)

    aux_inputs = [op("vae.epsilon", "Internal Gaussian sample", "sampling", sample,
                     "epsilon: [B,15]", ["torch.randn(z_mu.size(0), z_mu.size(1)).to(device)",
                                          "created inside reparameterize; not a user input"],
                     stochastic=True, origin="internal_random_source", learnable=False)]
    extra_edges = [
        dict(src="vae.epsilon", dst="vae.noise_product", role="random_sample",
             label="epsilon", src_port="out", dst_port="epsilon"),
        dict(src="vae.mu", dst="vae.encoder_return", role="retained_value",
             label="mu", src_port="out", dst_port="mu"),
        dict(src="vae.logvar", dst="vae.encoder_return", role="retained_value",
             label="logvar", src_port="out", dst_port="logvar"),
        dict(src="vae.mu", dst="vae.return", role="retained_value",
             label="mu", src_port="out", dst_port="mu"),
        dict(src="vae.logvar", dst="vae.return", role="retained_value",
             label="logvar", src_port="out", dst_port="logvar"),
        dict(src="vae.z", dst="vae.return", role="retained_value",
             label="encoded z", src_port="out", dst_port="encoded"),
    ]
    visual_roles = {
        "vae.root": "root", "vae.forward": "group", "vae.encoder": "encoder",
        "vae.decoder": "decoder", "vae.posterior": "ffn",
        "vae.mean_head": "inner", "vae.logvar_head": "inner",
        "vae.sampling": "sampling", "vae.sample_operands": "inner",
        "vae.scaled_noise": "inner", "vae.epsilon": "sampling",
        "vae.mean_operand": "tensor", "vae.half_logvar": "tensor",
        "vae.std": "activation", "vae.z": "norm", "vae.noise_product": "norm",
        "vae.enc_activation": "activation", "vae.dec_activation": "activation",
        "vae.dec_sigmoid": "softmax", "vae.input": "input", "vae.return": "output",
    }
    return dict(
        key="vae", name="VAE (MNIST fully connected)", source_project="deeplearning-models",
        entry=forward,
        profile=dict(task="MNIST reconstruction", mode="forward incl. stochastic sampling",
                     num_features=784, num_hidden_1=500, num_latent=15,
                     leaky_relu_negative_slope=0.0001, batch_axis="B",
                     batch_size_setting=128, input_range=[0, 1],
                     decoder_output="784 sigmoid pixel probabilities",
                     output_tuple=["z_mean", "z_log_var", "encoded", "decoded"],
                     external_input="flattened features", random_source="internal torch.randn",
                     likelihood="Bernoulli reconstruction", training_loss_in_forward=False),
        profile_label="MNIST 784 / hidden 500 / latent 15 / independent posterior heads",
        tree=tree, aux_inputs=aux_inputs, extra_edges=extra_edges,
        visual_roles=visual_roles,
        fill_width=["vae.forward", "vae.encoder", "vae.decoder", "vae.posterior", "vae.sampling"],
        facts=[
            "hidden_1 feeds two independent Linear heads: z_mean and z_log_var.",
            "z_log_var represents log variance; standard deviation is exp(logvar/2).",
            "epsilon is created by torch.randn inside reparameterize and is not an external feature input.",
            "This source samples in both train and eval; no training guard chooses mu instead of z.",
            "encoder returns (mu, logvar, encoded); decoder consumes only encoded.",
            "forward returns (mu, logvar, encoded, decoded), not only reconstruction.",
            "The KL sum and binary cross entropy are computed in the notebook training loop, outside forward.",
            "The decoder uses Linear 15->500->784, LeakyReLU then Sigmoid; no convolution or deconvolution.",
            "The graph represents the selected reconstruction call; standalone decoder(rand_features) generation is a separate call.",
        ],
        corrections=[
            "A generic VAE chart must show independent mean/log-variance heads, not one shared posterior Linear.",
            "Sampling must use exp(logvar/2) and an independent epsilon operand, not variance as standard deviation.",
            "The four-field forward tuple and the retained statistics are visible; drawing only reconstructed pixels omits returned values.",
            "KL/BCE, optimizer, and dataset flattening are caller operations; no loss node is inserted into model.forward.",
            "There is no Conv/BatchNorm/transposed-Conv stack in this supplied fully connected implementation.",
        ],
        symbols={SOURCE: ["VariationalAutoencoder", "VariationalAutoencoder.__init__",
                          "VariationalAutoencoder.reparameterize", "VariationalAutoencoder.encoder",
                          "VariationalAutoencoder.decoder", "VariationalAutoencoder.forward"]},
        legend=["B: batch; image 1x28x28 -> caller flatten 784; latent width 15",
                "input pink / forward return purple / LeakyReLU and exponential gray / Sigmoid green",
                "side routes retain tuple fields; epsilon side route is an internal random source",
                "same operator color does not mean shared weights; five Linear modules are independent"],
        config_files=[SOURCE],
    )

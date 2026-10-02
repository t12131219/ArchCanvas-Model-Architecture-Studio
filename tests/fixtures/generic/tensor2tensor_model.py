class T2TModel:
    pass


def transformer_prepare_encoder(inputs, target_space, hparams):
    return inputs, target_space, None


def transformer_prepare_decoder(targets, hparams):
    return targets, targets


def transformer_encoder(states, attention_bias, hparams):
    return states


def transformer_decoder(states, memory, self_bias, memory_bias, hparams):
    return states


class Transformer(T2TModel):
    def model_fn_body(self, features):
        hparams = self.hparams
        targets = features["targets"]
        inputs = features.get("inputs")
        target_space = features.get("target_space_id")
        encoder_input, encoder_attention_bias, _ = transformer_prepare_encoder(
            inputs, target_space, hparams
        )
        decoder_input, decoder_self_attention_bias = transformer_prepare_decoder(
            targets, hparams
        )
        encoder_output = transformer_encoder(
            encoder_input, encoder_attention_bias, hparams
        )
        decoder_output = transformer_decoder(
            decoder_input,
            encoder_output,
            decoder_self_attention_bias,
            encoder_attention_bias,
            hparams,
        )
        return decoder_output

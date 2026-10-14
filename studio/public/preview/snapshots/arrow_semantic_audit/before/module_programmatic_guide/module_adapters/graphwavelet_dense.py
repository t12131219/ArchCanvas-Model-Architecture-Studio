from module_adapters._graphwavelet_support import SOURCE,definitions,build_wavelet,validate_wavelet
KEY='graphwavelet_dense';LINKS,REQUIRED=definitions(False)
CONTRACTS=[('GraphWaveletLayer.define_parameters','torch.nn.Parameter(torch.Tensor(self.in_channels, self.out_channels))'),('DenseGraphWaveletLayer.forward','spspmm(phi_indices, phi_values, self.diagonal_weight_indices, self.diagonal_weight_filter.view(-1), self.ncount, self.ncount, self.ncount)'),('DenseGraphWaveletLayer.forward','spspmm(rescaled_phi_indices, rescaled_phi_values, phi_inverse_indices, phi_inverse_values, self.ncount, self.ncount, self.ncount)'),('DenseGraphWaveletLayer.forward','torch.mm(features, self.weight_matrix)'),('DenseGraphWaveletLayer.forward','spmm(phi_product_indices, phi_product_values, self.ncount, self.ncount, filtered_features)')]
def build():return build_wavelet(KEY,False)
def validate_ir(ir):return validate_wavelet(ir,KEY,False)

import pandas as pd
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler, MaxAbsScaler, PowerTransformer,\
    QuantileTransformer, FunctionTransformer
from sklearn.decomposition import PCA, KernelPCA, IncrementalPCA, FastICA, SparsePCA
from PyEMD import EMD, EEMD
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

from dl4seq.utils.utils import dateandtime_now

# TODO add logistic, tanh and more scalers.


class EmdTransformer(object):
    """Empirical Mode Decomposition"""
    def __init__(self, ensemble=False, **kwargs):
        self.ensemble = ensemble
        if ensemble:
            self.emd_obj = EEMD(**kwargs)
        else:
            self.emd_obj = EMD(**kwargs)

    def fit_transform(self, data, **kwargs):

        if isinstance(data, pd.DataFrame):
            data = data.values
        else:
            assert isinstance(data, np.ndarray)

        assert len(data.shape) == 2

        imfs = []
        for col in range(data.shape[1]):

            if self.ensemble:
                IMFs = self.emd_obj.eemd(data[:, col], **kwargs)
            else:
                IMFs = self.emd_obj.emd(data[:, col], **kwargs)

            imfs.append(IMFs.T)

        return np.concatenate(imfs, axis=1)

    def inverse_transform(self, **kwargs):
        raise NotImplementedError


class scaler_container(object):

    def __init__(self):
        self.scalers = {}

class Transformations(scaler_container):
    """
    Apply transformation to data.
    Any new transforming methods should define two methods one starting with "transform_with_" and "inverse_transofrm_with_"
    https://developers.google.com/machine-learning/data-prep/transform/normalization

    ---------
    arguments
    ---------
     - data: a dataframe or numpy ndarray. The transformed or inversely transformed value will have the same type as data
             and will have the same index as data (in case data is dataframe).
     - method: str, method by which to transform and consequencly inversely transform the data. default is 'minmax'.
                Currently following methods are available for transformation and inverse transformation
                  minmax
                  maxabs
                  robust
                  power
                  zscore:
                  quantile:
                  log:     logrithmic
                  tan:     tangent
                  cumsum:  cummulative sum
                  pca:     principle component analysis
                  kpca:    kernel component analysis
                  ipca:    incremental principle component analysis
                  fastica: fast incremental component analysis

                Following methods have only transformations and not inverse transformations. They can be used for feature
                creation.
                  emd:    empirical mode decomposition
                  eemd:   ensemble empirical mode decomposition

     - features: list of strings, if data is datafrmae, then this list is the features on which we want to apply transformation.
                 The remaining columns will remain same/unchanged.
     - replace_nans: bool, If true, then will replace the nan values in data with some fixed value `replace_with` before
                     transformation.
     - replace_with: str/int/float, if replace_nans is True, then this value will be used to replace nans in dataframe
                      before doing transformation.
     - kwargs: any arguments provided to be provided to transformer on INTIALIZATION and not during transform or inverse
                    transform e.g. n_components for pca.

    To transform a datafrmae using any of the above methods use
        scaler = Scalers(data=df, method=method)
        scaler.transform()
      or
        scaler = Scalers(data=df)
        normalized_df4, scaler_dict = scaler.transform_with_method()
      or
        scaler = Scalers(data=df, method=method)
        normalized_df, scaler_dict = scaler()
      or using one liner
        normalized_df, scaler = Scalers(data=df, method=method, features=cols)('normalize')
    where `method` can be any of the above mentioned methods.
    """

    available_scalers = {
        "minmax": MinMaxScaler,
        "zscore": StandardScaler,
        "robust": RobustScaler,
        "maxabs": MaxAbsScaler,
        "power": PowerTransformer,
        "quantile": QuantileTransformer,
        "pca": PCA,
        "kpca": KernelPCA,
        "ipca": IncrementalPCA,
        "fastica": FastICA,
        "sparsepca": SparsePCA,
        "emd": EmdTransformer,
        "eemd": EmdTransformer,
    }

    dim_expand_methods = ['emd', 'eemd']
    dim_red_methods = ["pca", "kpca", "ipca", "fastica", "sparsepca"]  # dimensionality reduction methods
    mod_dim_methods = dim_red_methods + dim_expand_methods

    def __init__(self,
                 data: pd.DataFrame,
                 method:str = 'minmax',
                 features=None,
                 replace_nans = False,
                 replace_with='mean',
                 **kwargs):

        super().__init__()

        self.method = method
        self.replace_nans=replace_nans
        self.replace_with=replace_with
        data = self.pre_process_data(data.copy())
        self.data = data

        self.features = features
        self.initial_shape = data.shape
        self.kwargs = kwargs
        self.transformed_features = None

    def __call__(self, what="transform", return_key=False, **kwargs):

        if what.upper().startswith("TRANS"):

            return self.transform(return_key=return_key, **kwargs)

        elif what.upper().startswith("INV"):

            return self.inverse_transform(**kwargs)

        else:
            raise ValueError(f"The class Transformation can not be called with keyword argument 'what'={what}")

    def __getattr__(self, item):

        if item.startswith('_'):
            return self.__getattribute__(item)
        elif item.startswith("transform_with"):
            transformer = item.split('_')[2]
            if transformer.lower() in list(self.available_scalers.keys()) + ["log", "tan", "cumsum"]:
                self.method = transformer
                return self.transform_with_sklearn
        elif item.startswith("inverse_transform_with"):
            transformer = item.split('_')[3]
            if transformer.lower() in list(self.available_scalers.keys()) + ["log", "tan", "cumsum"]:
                self.method = transformer
                return self.inverse_transform_with_sklearn

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, x):
        if isinstance(x, pd.DataFrame):
            self._data = x
        else:
            assert isinstance(x, np.ndarray)
            xdf = pd.DataFrame(x, columns=['data'+str(i) for i in range(x.shape[1])])
            self._data = xdf

    @property
    def features(self):
        return self._features

    @features.setter
    def features(self, x):
        if x is None:
            self._features = list(self.data.columns)
        else:
            self._features = x

    @property
    def transformed_features(self):
        return self._transformed_features

    @transformed_features.setter
    def transformed_features(self, x):
        self._transformed_features = x

    @property
    def num_features(self):
        return len(self.features)

    @property
    def change_dim(self):
        if self.method.lower() in self.mod_dim_methods:
            return True
        else:
            return False

    def get_scaler(self):

        return self.available_scalers[self.method.lower()]

    def pre_process_data(self, data):
        """Makes sure that data is dataframe and optionally replaces nans"""
        if isinstance(data, pd.DataFrame):
            data = data
        else:
            assert isinstance(data, np.ndarray)
            data = pd.DataFrame(data, columns=['data'+str(i) for i in range(data.shape[1])])

        # save the index if not already saved so that can be used later
        if self.index is None:
            self.index = data.index

        if self.replace_nans:
            indices = {}

            for col in data.columns:

                i = data[col].index[data[col].apply(np.isnan)]
                if len(i) > 0:
                    indices[col] = i.values
                    # replace nans with values
                    data[col][indices[col]] = get_val(data[col], self.replace_with)

            # because pre_processing is implemented 2 times, we don't want to overwrite nan_indices
            if self.nan_indices is None: self.nan_indices = indices

            if len(indices) > 0:
                if self.method.lower() == "cumsum":
                    print("Warning: nan values found and they may cause problem")
        return data

    def post_process_data(self, data):
        """If nans were replaces with some value, put nans back."""
        if self.replace_nans:
            if hasattr(self, 'nan_indices'):

                for col, idx in self.nan_indices.items():
                    data[col][idx] = np.nan

        return data

    def transform_with_sklearn(self, return_key=False, **kwargs):

        if self.method.lower() == "log":
            scaler = FunctionTransformer(func=np.log, inverse_func=np.exp, validate=True, check_inverse=True)
        elif self.method.lower() == "tan":
            scaler = FunctionTransformer(func=np.tan, inverse_func=np.tanh, validate=True, check_inverse=False)
        elif self.method.lower() == "cumsum":
            scaler = FunctionTransformer(func=np.cumsum, inverse_func=np.diff, validate=True, check_inverse=False,
                                         kw_args={"axis": 0}, inv_kw_args={"axis": 0, "append": 0})
        else:
            scaler = self.get_scaler()(**self.kwargs)

        to_transform = self.get_features()  #TODO, shouldn't kwargs go here as input?

        data = scaler.fit_transform(to_transform, **kwargs)

        if self.method.lower() in self.mod_dim_methods:
            features = [self.method.lower() + str(i+1) for i in range(data.shape[1])]
            data = pd.DataFrame(data, columns=features)
            self.transformed_features = features
            self.features = features
        else:
            data = pd.DataFrame(data, columns=to_transform.columns)

        scaler = self.serialize_scaler(scaler, to_transform)

        data = self.maybe_insert_features(data)

        data = self.post_process_data(data)

        self.tr_data = data
        if return_key:
            return data, scaler
        return data

    def inverse_transform_with_sklearn(self, **kwargs):

        scaler = self.get_scaler_from_dict(**kwargs)

        to_transform = self.get_features(**kwargs)

        data = scaler.inverse_transform(to_transform)

        if self.method.lower() in self.mod_dim_methods:
            # now use orignal data columns names, but if the class is being directly called for inverse transform
            # then we don't know what cols were transformed, in that scenariio use dummy col name.
            cols = ['data'+str(i) for i in range(data.shape[1])] if self.transformed_features is None else self.data.columns
            data = pd.DataFrame(data, columns=cols)
        else:
            data = pd.DataFrame(data, columns=to_transform.columns)

        data = self.maybe_insert_features(data)

        data = self.post_process_data(data)

        return data

    def transform(self, return_key=False, **kwargs):

        return getattr(self, "transform_with_" + self.method.lower())(return_key=return_key, **kwargs)

    def inverse_transform(self, **kwargs):

        if 'key' in kwargs or 'scaler' in kwargs:
            pass
        elif len(self.scalers) ==1:
            kwargs['scaler'] = self.scalers[list(self.scalers.keys())[0]]['scaler']

        return getattr(self, "inverse_transform_with_" + self.method.lower())(**kwargs)

    def get_features(self, **kwargs) -> pd.DataFrame:
        # use the provided data if given otherwise use self.data
        data = kwargs['data'] if 'data' in kwargs else self.data

        if self.replace_nans:
            data = self.pre_process_data(data)

        if self.features is None:
            return data
        else:
            assert isinstance(self.features, list)
            return data[self.features]

    def serialize_scaler(self, scaler, to_transform):
        key = self.method + str(dateandtime_now())
        serialized_scaler = {
            "scaler": scaler,
            "shape": to_transform.shape,
            "key": key
        }
        self.scalers[key] = serialized_scaler

        return serialized_scaler

    def get_scaler_from_dict(self, **kwargs):
        if 'scaler' in kwargs:
            scaler = kwargs['scaler']
        elif 'key' in kwargs:
            scaler = self.scalers[kwargs['key']]['scaler']
        else:
            raise ValueError("provide scaler or key")
        return scaler

    def maybe_insert_features(self, trans_df):

        if self.index is not None:
            trans_df.index = self.index

        transformed_features = len(self.transformed_features) if self.transformed_features is not None else len(trans_df.columns)
        num_features = len(self.data.columns) if self.method.lower() not in self.mod_dim_methods else transformed_features
        if len(trans_df.columns) != num_features:
            df = pd.DataFrame(index=self.index)
            for col in self.data.columns: #features:
                if col in trans_df.columns:
                    _df = trans_df[col]
                else:
                    _df = self.data[col]

                df = pd.concat([df, _df], axis=1, sort=True)
        else:
            df = trans_df

        if not self.change_dim:
            assert df.shape == self.initial_shape
        return df

    def plot_pca(self, target:np.ndarray, pcs:np.ndarray=None, labels:list=None, save=False, dim="3d"):

        if pcs is None:
            pcs = self.tr_data.values
            labels = list(self.tr_data.columns) if labels is None else labels

        if labels is not None:
            assert len(labels) == pcs.shape[1]
        else:
            labels = self.transformed_features

        if dim.upper() == "3D":
            self.plot_pca3d(target, pcs, labels, save)
        elif dim.upper() == "2D":
            self.plot_pca2d(target, pcs, labels, save)
        else:
            raise ValueError

    def plot_pca3d(self, target, pcs, labels, save):

        fig = plt.figure(1, figsize=(4, 3))
        plt.clf()
        ax = Axes3D(fig, rect=[0, 0, .95, 1], elev=48, azim=134)

        plt.cla()
        for label, name in enumerate(labels):
            ax.text3D(pcs[target == label, 0].mean(),
                      pcs[target == label, 1].mean() + 1.5,
                      pcs[target == label, 2].mean(), name,
                      horizontalalignment='center',
                      bbox=dict(alpha=.5, edgecolor='w', facecolor='w'))
        # Reorder the labels to have colors matching the cluster results
        target = np.choose(target, [1, 2, 0]).astype(np.float)

        ax.scatter(pcs[:, 0], pcs[:, 1], pcs[:, 2], c=target, cmap=plt.cm.nipy_spectral,
               edgecolor='k')

        ax.xaxis.set_ticklabels([])
        ax.yaxis.set_ticklabels([])
        ax.zaxis.set_ticklabels([])

        end_fig(save)
        return

    def plot_pca2d(self, target, pcs, labels, save):

        for i, target_name in zip([0, 1, 2], labels):
            plt.scatter(pcs[target == i, 0], pcs[target == i, 1], alpha=.8, lw=2,
                        label=target_name)
        plt.legend(loc='best', shadow=False, scatterpoints=1)
        plt.title('PCA of IRIS dataset')
        end_fig(save)
        return


def get_val(df:pd.DataFrame, method):

    if isinstance(method, str):
        if method.lower() == "mean":
            return df.mean()
        elif method.lower() == "max":
            return df.max()
        elif method.lower() == "min":
            return df.min()
    elif isinstance(method, int) or isinstance(method, float):
        return method
    else:
        raise ValueError(f"unknown method {method} to replace nan vlaues")


def end_fig(save):
    if save is None:
        pass
    elif save:
        plt.savefig('pca')
    else:
        plt.show()
    plt.close('all')
    return
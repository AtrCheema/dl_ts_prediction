from skopt import BayesSearchCV
import os
from sklearn.model_selection import GridSearchCV, RandomizedSearchCV
from skopt import gp_minimize
from skopt.utils import use_named_args
from sklearn.model_selection import ParameterGrid, ParameterSampler
import numpy as np
from TSErrors import FindErrors
import json

from dl4seq import Model
from dl4seq.utils import make_model
from dl4seq.utils.utils import post_process_skopt_results


class HyperOpt(object):
    """
    Combines the power of sklearn based GridSeearchCV, RandomizeSearchCV and skopt based BayeSearchCV.
    Complements the following two deficiences of sklearn
      - sklearn based SearchCVs apply only on sklearn based models and not on such as on NNs
      - sklearn does not provide Bayesian optimization
    On the other hand BayesSearchCV of skopt library
      - extends sklearn that the sklearn-based regressors/classifiers could be used for Bayesian but then it can be used
        used for sklearn-based regressors/classifiers
      - The gp_minimize function from skopt allows application of Bayesian on any regressor/classifier/model, but in that
        case this will only be Bayesian

    We with to make a class which allows application of any of the three optimization methods on any type of model/classifier/regressor.
    The way should be that if the classifier/regressor is of sklearn-based, then for random search, we should be using
    RanddomSearchCV, for grid search, it should be using GridSearchCV and for Bayesian, it should be using BayesSearchCV.
    On the other hand, if the model is not from sklearn-based, we should still be able to implement any of the three methods.
    In such case, the bayesian will be implemented using gp_minimize. Random search and grid search will be done by
    simple iterating over the sample space generated as in sklearn based samplers. However, the post-processing of the
    results should be done same as done on RandomSearchCV and GridSearch CV.

    Thus one motivation of this class is to unify GridSearchCV, RandomSearchCV and BayesSearchCV by complimenting each other.
    The second motivation is to extend their abilities.

    All of the above should be done without limiting the capabilities of GridSearchCV, RandomSearchCV and BayesSearchCV
    or complicating their use.

    The class should pass all the tests written in sklearn or skopt for corresponding classes.

    BayesSearchCV also inherits from BaseSearchCV as GridSearchCV and RandomSearchCV do.

    :Scenarios
    ---------------
    Use scenarios of this class can be one of the following:
      1) Apply grid/random/bayesian search for sklearn based regressor/classifier
      2) Apply grid/random/bayesian search for custom regressor/classifier/model/function such as for xgboost
      3) Apply grid/random/bayesian search for dl4seq. This may be the easierst one, if user is familier with dl4seq


    :parameters
    --------------
    method: str, must be one of "random", "grid" and "bayes", defining which optimization method to use.
    model: callable, It can be either sklearn/xgboost based regressor/classifier or any function whose returned values
                     can act as objective function for the optimization problem.
    param_space: list/dict, the parameters to be optimized. Based upon above scenarios
                   - For scenario 1, if `method` is "grid", then this argument will be passed to GridSearchCV of sklearn
                       as `param_grid`.  If `method` is "random", then these arguments will be passed to RandomizeSearchCV
                       of sklearn as `param_distribution`.  If `method` is "bayes",  then this must be a
                       dictionary of parameter spaces and this argument will be passed to `BayesSearchCV` as
                       `search_spaces`.
                   - If you are using your custom function as `model`, and "method` is "bayes", then this must be either
                     dictionary of parameter spaces or a list of tuples defining upper and lower bounds of each parameter
                     of the custom function which you used as `model`. These tuples must follow the same sequence as the
                     order of input parameters in your custom model/function. This argument will then be provided to
                     `gp_minnimize` function of skopt. This case will the :ref:`<example>(4) in skopt.



    References
    --------------
    1 https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.GridSearchCV.html#sklearn.model_selection.GridSearchCV
    2 https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.RandomizedSearchCV.html#sklearn.model_selection.RandomizedSearchCV
    3 https://scikit-optimize.github.io/stable/modules/generated/skopt.BayesSearchCV.html
    4 https://github.com/scikit-optimize/scikit-optimize/blob/9334d50a1ad5c9f7c013a1c1cb95313a54b83168/examples/bayesian-optimization.py#L109

    """

    def __init__(self,
                 method:str, *,
                 param_space,
                 model=None,
                 **kwargs
                 ):

        if method not in ["random", "grid", "bayes"]:
            raise ValueError("method must be one of random, grid or bayes.")

        self.model = model
        self.method = method
        self.param_space=param_space
        self.dl4seq_args = None
        self.use_named_args = False
        self.title = self.method

        self.gpmin_args = self.check_args(**kwargs)

        if self.use_sklearn():
            if self.method == "random":
                self.optfn = RandomizedSearchCV(estimator=model, param_distributions=param_space, **kwargs)
            else:
                self.optfn = GridSearchCV(estimator=model, param_grid=param_space, **kwargs)

        elif self.use_skopt_bayes:
            self.optfn = BayesSearchCV(estimator=model, search_spaces=param_space, **kwargs)

        elif self.use_skopt_gpmin:
            self.fit = self.own_fit

        elif self.use_own:

            if self.method == "grid":
                self.fit = self.grid_search
            else:
                self.fit = self.random_search

    def check_args(self, **kwargs):
        kwargs = kwargs.copy()
        if "use_named_args" in kwargs:
            self.use_named_args = kwargs.pop("use_named_args")

        if "dl4seq_args" in kwargs:
            self.dl4seq_args = kwargs.pop("dl4seq_args")
            self.data = kwargs.pop("data")
        return kwargs

    def __getattr__(self, item):
        # TODO, not sure if this is the best way
        # Since it was not possible to inherit this class from BaseSearchCV and BayesSearchCV at the same time, this
        # hack makes sure that all the functionalities of GridSearchCV, RandomizeSearchCV and BayesSearchCV are also
        # available with class.
        if hasattr(self.optfn, item):
            return getattr(self.optfn, item)
        else:
            raise AttributeError(f"Attribute {item} not found")

    def use_sklearn(self):
        # will return True if we are to use sklearn's GridSearchCV or RandomSearchCV
        if self.method in ["random", "grid"] and "sklearn" in str(type(self.model)):
            return True
        return False

    @property
    def use_skopt_bayes(self):
        # will return true if we have to use skopt based BayesSearchCV
        if self.method=="bayes" and "sklearn" in str(type(self.model)):
            assert not self.use_sklearn()
            return True
        return False

    @property
    def use_skopt_gpmin(self):
        # will return True if we have to use skopt based gp_minimize function. This is to implement Bayesian on
        # non-sklearn based models
        if self.method == "bayes" and "sklearn" not in str(type(self.model)):
            assert not self.use_sklearn()
            assert not self.use_skopt_bayes
            return True
        return False

    @property
    def use_own(self):
        # return True, we have to build our own optimization method.
        if not self.use_sklearn() and not self.use_skopt_bayes and not self.use_skopt_gpmin:
            return True
        return False

    def dl4seq_model(self, **kwargs):

        config = make_model(ml_model_args=kwargs, **self.dl4seq_args)

        self.title = self.method + '_' + config["model_config"]["problem"] + '_' + config["model_config"]["ml_model"]
        model = Model(config,
                      data=self.data,
                      prefix=self.title,
                      verbosity=0)

        model.train(indices="random")

        t, p = model.predict(indices=model.test_indices, pref='test')
        mse = FindErrors(t, p).mse()
        print(f"Validation mse {mse}")

        return mse

    def dims(self):

        if isinstance(self.param_space, dict):
            return list(self.param_space.values())

        return list(self.param_space)

    def model_for_gpmin(self):
        """This function can be called in two cases:
            - The user has made its own model.
            - We make model using dl4seq and return the error.
          In first case, we just return what user has provided.
          """
        if callable(self.model) and not self.use_named_args:
            print('here')
            return self.model

        dims = self.dims()
        if self.use_named_args and self.dl4seq_args is None:

            @use_named_args(dimensions=dims)
            def fitness(**kwargs):
                return self.model(**kwargs)
            return fitness

        if self.use_named_args and self.dl4seq_args is not None:
            @use_named_args(dimensions=dims)
            def fitness(**kwargs):
                return self.dl4seq_model(**kwargs)
            return fitness

        raise ValueError(f"used named args is {self.use_named_args}")

    def own_fit(self):

        results = {}

        search_result = gp_minimize(func=self.model_for_gpmin(),
                                    dimensions=self.dims(),
                                    **self.gpmin_args)

        opt_path = os.path.join(os.getcwd(), "results\\" + self.title)
        if not os.path.exists(opt_path):
            os.makedirs(opt_path)
        post_process_skopt_results(search_result, results, opt_path)

        return search_result

    def eval_sequence(self, params):

        results = {}
        for para in params:

            err = self.dl4seq_model(**para)
            results[str(err)] = para

        with open(self.method + "_results.jsong", "w") as fp:
            json.dump(results, fp, sort_keys=True, indent=4)

        return results
    def grid_search(self):

        params = list(ParameterGrid(self.param_space))
        self.param_grid = params

        return self.eval_sequence(params)

    @property
    def random_state(self):
        if "random_state" not in self.gpmin_args:
            return np.random.RandomState(313)
        else:
            return np.random.RandomState(self.gpmin_args['random_state'])

    @property
    def iters(self):
        return self.gpmin_args['n_iter']

    def random_search(self):
        rng = self.random_state
        param_list = list(ParameterSampler(self.param_space, n_iter=self.iters,
                                           random_state=rng))

        return self.eval_sequence(param_list)

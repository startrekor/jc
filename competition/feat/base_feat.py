# coding:utf-8"""__file__    base_feat.py__description__    This file provides modules for combining features and save them in svmlight format.__author__    songquanwang"""import abcimport osimport cPicklefrom sklearn.datasets import dump_svmlight_fileimport numpy as npimport pandas as pdfrom scipy.sparse import hstackimport competition.conf.model_library_config as configfrom competition.feat.nlp import ngramfrom competition.feat.nlp.nlp_utils import preprocess_dataclass BaseFeat(object):    __metaclass__ = abc.ABCMeta    @staticmethod    def gen_temp_feat(df):        """        用户组合其他特征的临时特征，这些基本特征会用到        :param df:        :return:        """        ## unigram        print "generate unigram"        df["query_unigram"] = list(df.apply(lambda x: preprocess_data(x["query"]), axis=1))        df["title_unigram"] = list(df.apply(lambda x: preprocess_data(x["product_title"]), axis=1))        df["description_unigram"] = list(df.apply(lambda x: preprocess_data(x["product_description"]), axis=1))        ## bigram        print "generate bigram"        join_str = "_"        df["query_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["query_unigram"], join_str), axis=1))        df["title_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["title_unigram"], join_str), axis=1))        df["description_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["description_unigram"], join_str), axis=1))        ## trigram        print "generate trigram"        join_str = "_"        df["query_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["query_unigram"], join_str), axis=1))        df["title_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["title_unigram"], join_str), axis=1))        df["description_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["description_unigram"], join_str), axis=1))        return df    @staticmethod    def get_sample_indices_by_relevance(dfTrain, additional_key=None):        """            return a dict with            key: (additional_key, median_relevance)            val: list of sample indices        """        # 从零开始编号        dfTrain["sample_index"] = range(dfTrain.shape[0])        group_key = ["median_relevance"]        if additional_key != None:            group_key.insert(0, additional_key)        # 根据相关性分组 每组序号放到[]里        agg = dfTrain.groupby(group_key, as_index=False).apply(lambda x: list(x["sample_index"]))        # 生成相关性为键的字典        d = dict(agg)        dfTrain = dfTrain.drop("sample_index", axis=1)        return d    @staticmethod    def dump_feat_name(feat_names, feat_name_file):        """            save feat_names to feat_name_file        """        with open(feat_name_file, "wb") as f:            for i, feat_name in enumerate(feat_names):                if feat_name.startswith("count") or feat_name.startswith("pos_of"):                    f.write("('%s', SimpleTransform(config.count_feat_transform)),\n" % feat_name)                else:                    f.write("('%s', SimpleTransform()),\n" % feat_name)    def gen_feat(single_feat_path, combined_feat_path, feat_names, mode):        """        :param single_feat_path:        :param combined_feat_path:        :param feat_names:        :param mode        :return:        """        if not os.path.exists(combined_feat_path):            os.makedirs(combined_feat_path)        for i, (feat_name, transformer) in enumerate(feat_names):            ## load train feat            feat_train_file = "%s/train.%s.feat.pkl" % (single_feat_path, feat_name)            with open(feat_train_file, "rb") as f:                x_train = cPickle.load(f)            if len(x_train.shape) == 1:                x_train.shape = (x_train.shape[0], 1)            ## load test feat            feat_test_file = "%s/%s.%s.feat.pkl" % (single_feat_path, mode, feat_name)            with open(feat_test_file, "rb") as f:                x_test = cPickle.load(f)            if len(x_test.shape) == 1:                x_test.shape = (x_test.shape[0], 1)            ## align feat dim 补齐列？matrix hstack  tocsr 稀疏格式            dim_diff = abs(x_train.shape[1] - x_test.shape[1])            if x_test.shape[1] < x_train.shape[1]:                x_test = hstack([x_test, np.zeros((x_test.shape[0], dim_diff))]).tocsr()            elif x_test.shape[1] > x_train.shape[1]:                x_train = hstack([x_train, np.zeros((x_train.shape[0], dim_diff))]).tocsr()            ## apply transformation            x_train = transformer.fit_transform(x_train)            x_test = transformer.transform(x_test)            ## stack feat 多个属性列组合在一起            if i == 0:                X_train, X_test = x_train, x_test            else:                try:                    X_train, X_test = hstack([X_train, x_train]), hstack([x_test, x_test])                except:                    X_train, X_test = np.hstack([X_train, x_train]), np.hstack([x_test, x_test])            # > 右对齐 自动填充{}            print("Combine {:>2}/{:>2} feat: {} ({}D)".format(i + 1, len(feat_names), feat_name, x_train.shape[1]))        print "Feat dim: {}D".format(X_train.shape[1])        # train info 中获取label值        info_train = pd.read_csv("%s/train.info" % (combined_feat_path))        # change it to zero-based for multi-classification in xgboost        Y_train = info_train["median_relevance"] - 1        # test        info_test = pd.read_csv("%s/%s.info" % (combined_feat_path, mode))        Y_test = info_test["median_relevance"] - 1        # dump feat 生成所有的特征+label        dump_svmlight_file(X_train, Y_train, "%s/train.feat" % (combined_feat_path))        dump_svmlight_file(X_test, Y_test, "%s/%s.feat" % (combined_feat_path, mode))    @staticmethod    def combine_feat(feat_names, feat_path_name):        """        function to combine features        """        print("==================================================")        print("Combine features...")        # Cross-validation        print("For cross-validation...")        ## for each run and fold  把没Run每折train.%s.feat.pkl　文件读出来合并到一起　然后保存到        for run in range(1, config.n_runs + 1):            # use 33% for training and 67 % for validation, so we switch trainInd and validInd            for fold in range(1, config.n_folds + 1):                print("Run: %d, Fold: %d" % (run, fold))                # 单个feat path                path = "%s/Run%d/Fold%d" % (config.feat_folder, run, fold)                # 合并后的feat path                save_path = "%s/%s/Run%d/Fold%d" % (config.feat_folder, feat_path_name, run, fold)                BaseFeat.gen_feat(path, save_path, feat_names, "valid")        # Training and Testing        print("For training and testing...")        path = "%s/All" % (config.feat_folder)        save_path = "%s/%s/All" % (config.feat_folder, feat_path_name)        BaseFeat.gen_feat(path, save_path, feat_names, "valid")
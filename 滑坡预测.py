import numpy as np
import pandas as pd


all_dataset='lz_slide.xlsx'
pred_dataset='predict_slide.xlsx'
df_data=pd.read_excel(all_dataset)
pred_data=pd.read_excel(pred_dataset)

charac_entries=['Lithology','Land use']
target_entry='slide_state'
#将数据集中字符型数据转换成哑变量
charac_entries_value={}
for w in charac_entries:
    charac_entries_value[w]={v:k+1 for k,v in enumerate(df_data[w].unique())}

print(charac_entries_value)

def feature_extranction(df):
    df_matrix=pd.DataFrame()
    df_label=pd.DataFrame()
    for w in df:
        if w in charac_entries:
            df_matrix[w]=df[w].map(charac_entries_value[w])  #直接将字符串映射到数值类型
        elif w==target_entry:
            df_label[w]=df[w]
        elif df[w].dtype in [np.int64, np.float64]:
            df_matrix[w]=df[w]

    return df_matrix,df_label

df_matrix,df_label=feature_extranction(df_data)

print(df_matrix)

from sklearn.preprocessing import StandardScaler

NORMALIZE = True
if NORMALIZE:
    sscaler = StandardScaler() # StandardScaler from sklearn.preprocessing
    sscaler.fit(df_matrix) # fit training data to get mean and variance of each feature term

    df_matrix = pd.DataFrame(sscaler.transform(df_matrix), index=df_matrix.index, columns=df_matrix.columns)
    print (df_matrix)
    
    
df_matrix[target_entry]=df_label
print(df_matrix)

from sklearn import metrics
from sklearn.model_selection import KFold
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.ensemble import AdaBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
import copy
from sklearn.metrics import roc_curve,auc
import matplotlib.pyplot as plt

# Model=GradientBoostingClassifier
# Model=AdaBoostClassifier
# Model=RandomForestClassifier
Model=LogisticRegression


splits=5
kf=KFold(n_splits=splits)
auc_max=[]
all_tpr=[]
all_fpr=[]
all_clf=[]
for train_index,test_index in kf.split(df_matrix):
    df_train,df_test=df_matrix.iloc[train_index,:],df_matrix.iloc[test_index,:]
    train_labels=pd.DataFrame()
    valid_labels=pd.DataFrame()
    train_matrix=pd.DataFrame()
    valid_matrix=pd.DataFrame()
    for w in df_matrix:            #分别得到训练集和测试集以及各自的标签
        if w == target_entry:
            train_labels[w]=df_train[w]
            valid_labels[w]=df_test[w]
        else:
            train_matrix[w]=df_train[w]
            valid_matrix[w]=df_test[w]

    tmp_train_labels=train_labels.reset_index(drop=True)      #将dataframe转化成数组，方便后面拟合模型
    tmp_valid_labels=valid_labels.reset_index(drop=True)
    tmp_train_matrix=train_matrix.reset_index(drop=True)
    tmp_valid_matrix=valid_matrix.reset_index(drop=True)

#     print(tmp_train_labels)
#     print(tmp_train_matrix)
        
    if Model == GradientBoostingClassifier:
        #GBDT网格搜索参数
        test_paras = [('n_estimators',[50,200]),
                     ('max_depth',[2,3]),
                     ('learning_rate',[0.10]),
                     ('verbose',[1])]
        default_paras = {'n_estimators':50,
                        'max_depth':3,
                        'learning_rate':0.1,
                        'verbose':1}
    elif Model == AdaBoostClassifier:
        #AdaBoost
        test_paras = [('n_estimators',[50,200]),
                     ('algorithm',['SAMME.R','SAMME']),
                     ('learning_rate',[0.10, 1.0])]
        default_paras = {'n_estimators':50,
                        'algorithm':'SAMME.R',
                        'learning_rate':1.0}
    elif Model == RandomForestClassifier:
        #RandomForest
        test_paras = [('n_estimators',[100,200]),
                     ('criterion',['gini','entropy'])]
        default_paras = {'n_estimators':100,
                        'criterion':'gini'}
    elif Model == LogisticRegression:
        test_paras = [('penalty',['l1','l2']),
                     ('solver',['liblinear'])]
        default_paras = {'penalty':'l2',
                        'solver':'liblinear'}
    
    
    best_paras = {}
    display_flag = True
    # start simple grid search
    for ent, itr in test_paras:
        auc_scores = [] # used to store auc scores
        for v in itr:
            paras = copy.copy(default_paras)
            paras[ent] = v
            clf = Model(**paras)
#             print ("Fit model...")
            clf.fit(tmp_train_matrix,  np.ravel(tmp_train_labels)) # training
            tmp_valid_predict = clf.predict_proba(tmp_valid_matrix)[:, 1] # get predicting probs of class '1'
            auc_score = metrics.roc_auc_score(y_true=tmp_valid_labels, y_score=tmp_valid_predict)
#             print ("Finish training %s(%s=%s)..." % (Model.__name__, ent, v))
#             print ("AUC on validation set:%.6f" % auc_score)
            auc_scores.append(auc_score)
        idx_max = np.argmax(auc_scores)
        best_paras[ent] = itr[idx_max]
#     print ("Find best paras: %s" % best_paras)
    iter_max_auc = np.max(auc_score)
    auc_max.append(iter_max_auc)
    #根据网格搜索，得到当前最优参数下的AUC并输出roc曲线
    clf = Model(**best_paras)
    clf.fit(tmp_train_matrix, np.ravel(tmp_train_labels)) # training
    tmp_valid_predict = clf.predict_proba(tmp_valid_matrix)[:, 1] # get predicting probs of class '1'
    fpr,tpr,thresholds=metrics.roc_curve(y_true=tmp_valid_labels, y_score=tmp_valid_predict,pos_label=0)
    all_fpr.append(fpr)
    all_tpr.append(tpr)
    all_clf.append(clf)
    
#output the auc of every fold
outfile='auc_every fold.txt'
with open(outfile,'w') as w:
    w.write('number of fold for validation'+' auc under the best para\n')
    for k in range(splits):
        w.write(str(k+1)+'   '+str(round(auc_max[k],4))+'\n')
#拟合最大AUC下所对应的GBDT拟合函数
max_id=auc_max.index(max(auc_max))
clf=all_clf[max_id]
#output the importance of the features
feature_importance=pd.DataFrame(clf.feature_importances_, columns=['feature_importance'])
feature_names=[x for x in df_matrix.columns if x != target_entry]
feature_importance.loc[:,'feature_name']=feature_names
feature_importance.to_csv('feature_importance.csv',index=False)


#绘制ROC曲线
plt.figure()
lw=1
plt_label=0
plt.plot([0,1],[0,1],color='navy',lw=lw,linestyle='--')
plt.xlim([0.0,1.0])
plt.ylim([0.0,1.0])
plt.xlabel('False Positive Rate')
plt.ylabel('True Positive Rate')
marks=['-o', '-s', '-^', '-p', '-^']
for link in range(len(all_fpr)):
    plt_label+=1
    plt.plot(all_tpr[link],all_fpr[link], lw=lw,label='the '+str(plt_label)+'th'+' fold:'+'ROC curve (area=%0.5f)' % auc_max[link])
    
plt.legend(loc='lower right')
plt.show()


#读取预测数据集，并进行正则化处理
#将拟合的GBDT模型用于预测滑坡
pred_matrix=pd.DataFrame()
pred_label=pd.DataFrame()
pred_matrix,pred_label=feature_extranction(pred_data)
# print(pred_matrix)

#对预测数据进行正则化处理
NORMALIZE = True
if NORMALIZE:
    sscaler = StandardScaler() # StandardScaler from sklearn.preprocessing
    sscaler.fit(pred_matrix) # fit training data to get mean and variance of each feature term

    pred_matrix = pd.DataFrame(sscaler.transform(pred_matrix), index=pred_matrix.index, columns=pred_matrix.columns)
#     print(pred_matrix)

test_predict = clf.predict_proba(pred_matrix)[:, 1] # get predicting probs of class '1'

#输出预测dataframe
out_matrix=pd.DataFrame()
pred_matrix=pred_matrix
pred_matrix['slide probability']=test_predict


#output some result to file
pred_matrix.to_csv('slide_probability.csv',index=False)
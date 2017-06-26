#important libraries
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error
from sklearn.preprocessing import MinMaxScaler
from keras.models import Sequential
from keras.layers import Dense
from keras.layers import LSTM
from math import sqrt
from keras.wrappers.scikit_learn import KerasRegressor
from keras import regularizers

#data preparation

data = pd.read_csv('/home/Akai/Documents/dataset.csv')

#model parameters
step = 7
asp_neurons = 4
asp_epochs = 100
cc_neurons = 4
cc_epochs = 100
index_of_today = 23
common_input_layer = 16
common_hidden_layer = 8
onion_tomato_input_layer = 8
onion_tomato_hidden_layer = 4

#setting up LSTM environment

#frame a sequence as a supervised learning problem
def timeseries_to_supervised(data, lag=1):
	df = pd.DataFrame(data)
	columns = [df.shift(i) for i in range(1, lag+1)]
	columns.append(df)
	df = pd.concat(columns, axis=1)
	df.fillna(0, inplace=True)
	return df

# create a differenced series
def difference(dataset, interval=1):
	diff = list()
	for i in range(interval, len(dataset)):
		value = dataset[i] - dataset[i - interval]
		diff.append(value)
	return pd.Series(diff)

# invert differenced value
def inverse_difference(history, yhat, interval=1):
	return yhat + history[-interval]

# scale train and test data to [-1, 1]
def scale(train, test):
	# fit scaler
	scaler = MinMaxScaler(feature_range=(-1, 1))
	scaler = scaler.fit(train)
	# transform train
	train = train.reshape(train.shape[0], train.shape[1])
	train_scaled = scaler.transform(train)
	# transform test
	test = test.reshape(test.shape[0], test.shape[1])
	test_scaled = scaler.transform(test)
	return scaler, train_scaled, test_scaled

# inverse scaling for a forecasted value
def invert_scale(scaler, X, value):
	new_row = [x for x in X] + [value]
	array = np.array(new_row)
	array = array.reshape(1, len(array))
	inverted = scaler.inverse_transform(array)
	return inverted[0, -1]

# fit an LSTM network to training data
def fit_lstm(train, batch_size, nb_epoch, neurons):
	X, y = train[:, 0:-1], train[:, -1]
	X = X.reshape(X.shape[0], 1, X.shape[1])
	model = Sequential()
	model.add(LSTM(neurons, batch_input_shape=(batch_size, X.shape[1], X.shape[2]), stateful=True))
	model.add(Dense(1))
	model.compile(loss='mean_squared_error', optimizer='adam')
	for i in range(nb_epoch):
		model.fit(X, y, epochs=1, batch_size=batch_size, verbose=0, shuffle=False)
		model.reset_states()
	return model

# make a one-step forecast
def forecast_lstm(model, batch_size, X):
	X = X.reshape(1, 1, len(X))
	yhat = model.predict(X, batch_size=batch_size)
	return yhat[0,0]

#OP input
op1 = input('OP on f-day1: ')
op2 = input('OP on f-day2: ')
op3 = input('OP on f-day3: ')

#essential list declaration
skuid = []
sku = []
pre_demand = []
pre_cc = []
forecasted_demand = []
forecasted_cc = []
ac_demand = []
ac_cc = []
date = []

#unique SKU identifier
uniqueness =[]
for i in range(len(np.unique(data.SkuId))):
    uniqueness.append(np.unique(data.SkuId)[i])
    
uniqueness.remove(2108)
uniqueness.remove(43)

#to keep a count of inactive SKUs
count_null = 0

#predictive loop

for i in uniqueness:
    spe_data = data[data.SkuId == i].reset_index(drop=True)
    spe_data = spe_data.fillna(method='bfill', axis=0)
    spe_data = spe_data.fillna(method='ffill', axis=0)
    
    if pd.isnull(spe_data.AvgSP[10]):
        count_null+= 1
    else:
        act_demand = []
        for i in range(len(spe_data)):
            spe_data.CustomerCount[i] = spe_data.CustomerCount[i] + spe_data.MissedCust[i]
            act_demand.append(spe_data.OrderedQty[i] + spe_data.MissedDemand[i])

        spe_data['ActualDemand'] = pd.DataFrame({'ActualDemand':act_demand})

        duplicate_indices = []
        for i in range(len(spe_data)-1):
            if spe_data.DeliveryDate[i]==spe_data.DeliveryDate[i+1]:
                duplicate_indices.append(i)
            else:
                count = 0
        
        for i in range(len(duplicate_indices)):
            spe_data = spe_data.drop(spe_data.index[[duplicate_indices[i]]])
    
        spe_data = spe_data.reset_index(drop = True)
        
        #cleaning data
        for i in range(len(spe_data)):
            if spe_data.CustomerCount[i]<np.percentile(spe_data.CustomerCount, 3):
                spe_data.CustomerCount[i]=np.percentile(spe_data.CustomerCount, 3)
            elif spe_data.CustomerCount[i]>np.percentile(spe_data.CustomerCount, 97):
                spe_data.CustomerCount[i]=np.percentile(spe_data.CustomerCount, 97)
            else:
                riario=0
            if spe_data.ActualDemand[i]<np.percentile(spe_data.ActualDemand, 3):
                spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 3)
            elif spe_data.ActualDemand[i]>np.percentile(spe_data.ActualDemand, 97):
                spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 97)
            else:
                count=0
        
        onion_data = data[data.SkuId == 2108].reset_index(drop=True).fillna(method = 'bfill', axis = 0)
        dummy_variable1 = onion_data.AvgSP


        #Setting train quantity and model parameters
        r = len(spe_data)-step

        #creating input_variables and output_variable

        input_variables = pd.DataFrame({'Date':spe_data.DeliveryDate, 'CustomerCount':spe_data.CustomerCount, 'AvgSP':spe_data.AvgSP,  'OP':dummy_variable1})
        input_variables = input_variables.drop(labels = ['Date'], axis=1)

        output_variable = pd.DataFrame({'Date':spe_data.DeliveryDate, 'ActualDemand':spe_data.ActualDemand})
        output_variable = output_variable.drop(labels = ['Date'], axis=1)
        
        #Predicting AvgSP

        #AvgSP series
        series_asp = input_variables['AvgSP']

        #transform data to be stationary
        raw_values_asp = series_asp.values
        diff_values_asp = difference(raw_values_asp, 1)

        # transform data to be supervised learning
        supervised_asp = timeseries_to_supervised(diff_values_asp, 1)
        supervised_values_asp = supervised_asp.values

        # split data into train and test-sets
        train_asp, test_asp = supervised_values_asp[0:-step], supervised_values_asp[-step:]

        # transform the scale of the data
        scaler_asp, train_scaled_asp, test_scaled_asp = scale(train_asp, test_asp)

        # fit the model
        lstm_model_asp = fit_lstm(train_scaled_asp, 1, asp_epochs, asp_neurons)
        # forecast the entire training dataset to build up state for forecasting
        train_reshaped_asp = train_scaled_asp[:, 0].reshape(len(train_scaled_asp), 1, 1)
        train_fit_asp = lstm_model_asp.predict(train_reshaped_asp, batch_size=1)

        train_reshaped_asp1 = []
        for i in range(len(train_fit_asp)):
            train_reshaped_asp1.append(train_reshaped_asp[i][0])

        # walk-forward validation on the test data
        predictions_asp = list()
        for i in range(len(test_scaled_asp)):
	        # make one-step forecast
	        X_asp, y_asp = test_scaled_asp[i, 0:-1], test_scaled_asp[i, -1]
	        yhat_asp = forecast_lstm(lstm_model_asp, 1, X_asp)
	        # invert scaling
	        yhat_asp = invert_scale(scaler_asp, X_asp, yhat_asp)
	        # invert differencing
	        yhat_asp = inverse_difference(raw_values_asp, yhat_asp, len(test_scaled_asp)+1-i)
	        # store forecast
	        predictions_asp.append(yhat_asp)
	        expected_asp = raw_values_asp[len(train_asp) + i + 1]
	        print('Day=%d, Predicted_asp=%f, Expected_asp=%f' % (i+1, yhat_asp, expected_asp))

        # report performance
        rmse = sqrt(mean_squared_error(raw_values_asp[-step:], predictions_asp))
        print('Test RMSE: %.3f' % rmse)

        # line plot of observed vs predicted
        plt.figure(figsize = (12,8))
        plt.plot(train_reshaped_asp1, color = 'blue', label = 'actual_values')
        plt.plot(train_fit_asp, color = 'red', label = 'fitted_values')
        plt.ylabel('AvgSP')
        plt.legend()
        plt.title('Training fit on AvgSP')
        plt.show()

        #prediction graph
        plt.figure(figsize=(12,8))
        plt.plot(predictions_asp, color = 'red', label = 'predicted_values')
        plt.plot(raw_values_asp[r:], color = 'blue', label = 'actual_values')
        plt.legend()
        plt.ylabel('AvgSP')
        plt.title('Predictions of AvgSP')
        plt.show()


        #Predicting CustomerCount

        #CC series
        series_cc = input_variables.CustomerCount

        # transform data to be stationary
        raw_values_cc = series_cc.values
        diff_values_cc = difference(raw_values_cc, 1)

        # transform data to be supervised learning
        supervised_cc = timeseries_to_supervised(diff_values_cc, 1)
        supervised_values_cc = supervised_cc.values

        # split data into train and test-sets
        train_cc, test_cc = supervised_values_cc[0:-step], supervised_values_cc[-step:]

        # transform the scale of the data
        scaler_cc, train_scaled_cc, test_scaled_cc = scale(train_cc, test_cc)

        # fit the model
        lstm_model_cc = fit_lstm(train_scaled_cc, 1, cc_epochs, cc_neurons)

        # forecast the entire training dataset to build up state for forecasting
        train_reshaped_cc = train_scaled_cc[:, 0].reshape(len(train_scaled_cc), 1, 1)
        train_fit_cc = lstm_model_cc.predict(train_reshaped_cc, batch_size=1)

        train_reshaped_cc1 = []
        for i in range(len(train_fit_cc)):
            train_reshaped_cc1.append(train_reshaped_cc[i][0])

        # walk-forward validation on the test data
        predictions_cc = list()
        for i in range(len(test_scaled_cc)):
	        # make one-step forecast
	        X_cc, y_cc = test_scaled_cc[i, 0:-1], test_scaled_cc[i, -1]
	        yhat_cc = forecast_lstm(lstm_model_cc, 1, X_cc)
	        # invert scaling
	        yhat_cc = invert_scale(scaler_cc, X_cc, yhat_cc)
	        # invert differencing
	        yhat_cc = inverse_difference(raw_values_cc, yhat_cc, len(test_scaled_cc)+1-i)
	        # store forecast
	        predictions_cc.append(yhat_cc)
	        expected_cc = raw_values_cc[len(train_cc) + i + 1]
	        print('Day=%d, Predicted_cc=%f, Expected_cc=%f' % (i+1, yhat_cc, expected_cc))

        # report performance
        rmse_cc = sqrt(mean_squared_error(raw_values_cc[-step:], predictions_cc))
        print('Test RMSE: %.3f' % rmse_cc)
    
        # line plot of observed vs predicted
        plt.figure(figsize = (12,8))
        plt.plot(train_reshaped_cc1, color = 'blue', label = 'fitted_values')
        plt.plot(train_fit_cc, color = 'red', label = 'actual_values')
        plt.legend()
        plt.ylabel('CustomerCount')
        plt.title('Training fit on CustomerCount')
        plt.show()

        #prediction graph
        plt.figure(figsize = (12,8))
        plt.plot(predictions_cc, color = 'red', label = 'predicted_values')
        plt.plot(raw_values_cc[r:], color = 'blue', label = 'actual_values')
        plt.legend()
        plt.ylabel('CustomerCount')
        plt.title('Predictions of CustomerCount')
        plt.show()

        #Setting up dataframes for demand prediction

        forecasted_iv = pd.DataFrame({'AvgSP':predictions_asp , 'OP':input_variables.OP[r:], 'CustomerCount':predictions_cc}).reset_index(drop = True)


        training_iv = input_variables[:r].values
        training_ov = output_variable[:r].values
        test_iv = forecasted_iv.values
        test_ov = output_variable[r:].reset_index(drop = True)

        #Demand Model

        def demand_model():
            model = Sequential()
            model.add(Dense(common_input_layer, input_dim=3, kernel_initializer='normal', activation='linear', kernel_regularizer = regularizers.l1(l=0.1), activity_regularizer = regularizers.l1(l=0.1)))
            model.add(Dense(common_hidden_layer, kernel_initializer='normal', activation='linear'))
            model.add(Dense(1, kernel_initializer='normal'))
            #    Compile model
            model.compile(loss='mean_squared_error', optimizer='adam')
            return model

        #estimate Demand
        estimator = KerasRegressor(build_fn=demand_model)
        model_fit_d = estimator.fit(training_iv, training_ov, nb_epoch = 100, verbose = 0)
        training_fit_d = estimator.predict(training_iv)
        predictions_d = estimator.predict(test_iv)
        predicted_values_d = []
        for i in range(len(predictions_d)):
            predicted_values_d.append(predictions_d[i])

        plt.figure(figsize = (12,8))    
        plt.plot(training_fit_d, color = 'red', label = 'fitted_values')
        plt.plot(training_ov, color = 'blue', label = 'actual_values')
        plt.legend()
        plt.ylabel('Demand')
        plt.title('Training fit on Demand')
        plt.show()

        #evaluation

        rmse_demand = sqrt(mean_squared_error(test_ov, predicted_values_d))
        print(rmse_demand)

        plt.figure(figsize = (12,8))
        plt.plot(predicted_values_d, color = 'red', label = 'predicted_values')
        plt.plot(test_ov, color = 'blue', label = 'actual_values')
        plt.legend()
        plt.ylabel('Demand')
        plt.title('Predictions of Demand')
        plt.show()

        #Setting up 3-day forecast scenario

        #forecasts asp
        forecast_asp = []
        for i in range(3):
            forecast = forecast_lstm(lstm_model_asp, 1, np.array([test_scaled_asp[-1, -1]]))
            forecast_is = invert_scale(scaler_asp, np.array([test_scaled_asp[-1, -1]]), forecast)
            forecast_id = inverse_difference(raw_values_asp, forecast_is, 1)
            test_scaled_asp[:,-1]+=np.array([forecast])
            forecast_asp.append(forecast_id)


        #forecasts cc
        forecast_cc = []
        for i in range(3):
            forecast2 = forecast_lstm(lstm_model_cc, 1, np.array([test_scaled_cc[-1, -1]]))
            forecast2_is = invert_scale(scaler_cc, np.array([test_scaled_cc[-1, -1]]), forecast2)
            forecast2_id = inverse_difference(raw_values_cc, forecast2_is, 1)
            test_scaled_cc[:,-1]+=np.array([forecast2])
            forecast_cc.append(forecast2_id)

        forecast_op = [op1, op2, op3]

        further_forecast_iv = pd.DataFrame({'AvgSP':forecast_asp, 'CustomerCount':forecast_cc, 'OP':forecast_op})

        #forecast

        fpredictions_d = estimator.predict(further_forecast_iv.values)
        fpredicted_values_d = []
        for i in range(len(fpredictions_d)):
            fpredicted_values_d.append(fpredictions_d[i])
    
        print('Forecast input:')
        print(further_forecast_iv)
        print('Demand Forecast:')
        print(fpredicted_values_d)
    
        for i in range(3):
            skuid.append(spe_data.SkuId[i])
            sku.append(spe_data.SKUName[i])
            forecasted_demand.append(fpredicted_values_d[i])
            forecasted_cc.append(forecast_cc[i])
            ac_demand.append(test_ov.ActualDemand[i+step-3])
            ac_cc.append(input_variables.CustomerCount[i+r+step-3])
            pre_demand.append(predicted_values_d[i+step-3])
            pre_cc.append(predictions_cc[i+step-3])
            date.append(i+index_of_today)
            
#Predicting onion and tomato demand
for i in (43,2108):
    spe_data = data[data.SkuId == i].reset_index(drop = True)
    spe_data = spe_data.fillna(method = 'bfill', axis = 0)
    spe_data = spe_data.fillna(method = 'ffill', axis = 0)
    act_demand = []
    for i in range(len(spe_data)):
        spe_data.CustomerCount[i] = spe_data.CustomerCount[i] + spe_data.MissedCust[i]
        act_demand.append(spe_data.OrderedQty[i] + spe_data.MissedDemand[i])

    spe_data['ActualDemand'] = pd.DataFrame({'ActualDemand':act_demand})

    duplicate_indices = []
    for i in range(len(spe_data)-1):
        if spe_data.DeliveryDate[i]==spe_data.DeliveryDate[i+1]:
            duplicate_indices.append(i)
        else:
            count = 0
    
    for i in range(len(duplicate_indices)):
        spe_data = spe_data.drop(spe_data.index[[duplicate_indices[i]]])

    spe_data = spe_data.reset_index(drop = True)
    #cleaning data
    for i in range(len(spe_data)):
        if spe_data.ActualDemand[i]<np.percentile(spe_data.ActualDemand, 3):
            spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 3)
        elif spe_data.ActualDemand[i]>np.percentile(spe_data.ActualDemand, 97):
            spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 97)
        else:
            count=0
    
    
    series_d = spe_data['ActualDemand']
    #transform data to be stationary
    raw_values_d = series_d.values
    diff_values_d = difference(raw_values_d, 1)
    
    # transform data to be supervised learning
    supervised_d = timeseries_to_supervised(diff_values_d, 1)
    supervised_values_d = supervised_d.values

    # split data into train and test-sets
    train_d, test_d = supervised_values_d[0:-step], supervised_values_d[-step:]

    # transform the scale of the data
    scaler_d, train_scaled_d, test_scaled_d = scale(train_d, test_d)

    # fit the model
    lstm_model_d = fit_lstm(train_scaled_d, 1, asp_epochs, asp_neurons)
    # forecast the entire training dataset to build up state for forecasting
    train_reshaped_d = train_scaled_d[:, 0].reshape(len(train_scaled_d), 1, 1)
    train_fit_d = lstm_model_d.predict(train_reshaped_d, batch_size=1)

    train_reshaped_d1 = []
    for i in range(len(train_fit_d)):
        train_reshaped_d1.append(train_reshaped_d[i][0])

    # walk-forward validation on the test data
    predictions_d = list()
    for i in range(len(test_scaled_d)):
        # make one-step forecast
        X_d, y_d = test_scaled_d[i, 0:-1], test_scaled_d[i, -1]
        yhat_d = forecast_lstm(lstm_model_d, 1, X_d)
        #invert scaling
        yhat_d = invert_scale(scaler_d, X_d, yhat_d)
        #invert differencing
        yhat_d = inverse_difference(raw_values_d, yhat_d, len(test_scaled_d)+1-i)
        #store forecast
        predictions_d.append(yhat_d)
        expected_d = raw_values_d[len(train_d) + i + 1]
        print('Day=%d, Predicted_d=%f, Expected_d=%f' % (i+1, yhat_d, expected_d))

    # report performance
    rmse = sqrt(mean_squared_error(raw_values_d[-step:], predictions_d))
    print('Test RMSE: %.3f' % rmse)

    # line plot of observed vs predicted
    plt.figure(figsize = (12,8))
    plt.plot(train_reshaped_d1, color = 'blue', label = 'actual_values')
    plt.plot(train_fit_d, color = 'red', label = 'fitted_values')
    plt.ylabel('Demand')
    plt.legend()
    plt.title('Training fit on Demand')
    plt.show()

    #prediction graph
    plt.figure(figsize=(12,8))
    plt.plot(predictions_d, color = 'red', label = 'predicted_values')
    plt.plot(raw_values_d[r:], color = 'blue', label = 'actual_values')
    plt.legend()
    plt.ylabel('Demand')
    plt.title('Predictions of Demand')
    plt.show()
    
    forecast_d = []
    for i in range(3):
        forecast = forecast_lstm(lstm_model_d, 1, np.array([test_scaled_d[-1, -1]]))
        forecast_is = invert_scale(scaler_d, np.array([test_scaled_d[-1, -1]]), forecast)
        forecast_id = inverse_difference(raw_values_d, forecast_is, 1)
        test_scaled_d[:,-1]+=np.array([forecast])
        forecast_d.append(forecast_id)
            
    for i in range(3):
        skuid.append(spe_data.SkuId[i])
        sku.append(spe_data.SKUName[i])
        forecasted_demand.append(forecast_d[i])
        ac_demand.append(spe_data.ActualDemand[i+r+step-3])
        pre_demand.append(predictions_d[i+step-3])
        date.append(i+index_of_today)
        

pred = pd.DataFrame({'SkuId':skuid, 'SKUName':sku, 'actual_demand':ac_demand, 'predicted_demand':np.round(pre_demand), 'actual_customers':ac_cc})
fore = pd.DataFrame({'SkuId':skuid, 'SKUName':sku, 'demand':np.round(forecasted_demand), 'customers':np.round(forecasted_cc), 'DeliveryDate':date})

pred.to_csv('Performance_normal_SKUs.csv')
fore.to_csv('Forecast_normal_SKUs.csv')

#For random volume SKUs

count_null2 = 0

for i in (2108, 43, 10, 21, 34, 45, 76, 124, 144, 769, 1835):
    spe_data = data[data.SkuId == i].reset_index(drop=True)
    spe_data = spe_data.fillna(method='bfill', axis=0)
    spe_data = spe_data.fillna(method='ffill', axis=0)
    
    if pd.isnull(spe_data.AvgSP[10]):
        count_null2+= 1
    else:
        act_demand = []
        for i in range(len(spe_data)):
            spe_data.CustomerCount[i] = spe_data.CustomerCount[i] + spe_data.MissedCust[i]
            act_demand.append(spe_data.OrderedQty[i] + spe_data.MissedDemand[i])

        spe_data['ActualDemand'] = pd.DataFrame({'ActualDemand':act_demand})

        duplicate_indices = []
        for i in range(len(spe_data)-1):
            if spe_data.DeliveryDate[i]==spe_data.DeliveryDate[i+1]:
                duplicate_indices.append(i)
            else:
                count = 0
        
        for i in range(len(duplicate_indices)):
            spe_data = spe_data.drop(spe_data.index[[duplicate_indices[i]]])
    
        spe_data = spe_data.reset_index(drop = True)
        
        #cleaning data
        for i in range(len(spe_data)):
            if spe_data.CustomerCount[i]<np.percentile(spe_data.CustomerCount, 3):
                spe_data.CustomerCount[i]=np.percentile(spe_data.CustomerCount, 3)
            elif spe_data.CustomerCount[i]>np.percentile(spe_data.CustomerCount, 97):
                spe_data.CustomerCount[i]=np.percentile(spe_data.CustomerCount, 97)
            else:
                riario=0
            if spe_data.ActualDemand[i]<np.percentile(spe_data.ActualDemand, 3):
                spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 3)
            elif spe_data.ActualDemand[i]>np.percentile(spe_data.ActualDemand, 97):
                spe_data.ActualDemand[i]=np.percentile(spe_data.ActualDemand, 97)
            else:
                count=0
                
        series_d = spe_data['ActualDemand] 
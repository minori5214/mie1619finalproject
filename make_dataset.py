import os

from mip_lazy import MIP
from cp_v2 import CP
from adaptive_lns_v3 import ALNS_Agent
from result import Result

import csv
import numpy as np
from copy import copy

skip_list = ['d1655.tsp', 'd2103.tsp', 'fl3795.tsp'] # CP cannot solve

def make_raw_data_rnn_switching(dir, t=20, T=300, save_to_csv=True):
    if save_to_csv:
        with open('rawdata_rnn_t{}_T{}.csv'.format(t, T), 'a') as f:
            f.write('Model, Instance, t, objVal, Status' + '\n')

    for file in os.listdir(dir):
        if file in skip_list:
            continue
        print("file name: ", file)
        time = 0
        status = 9
        best_result = Result(float('inf'), None, None)

        base = {}
        # Initialize the model
        base['MIP'] = MIP(os.path.join(dir, file), verbose=0)
        base['CP'] = CP(os.path.join(dir, file), verbose=0)
        base['ALNS'] = ALNS_Agent(os.path.join(dir, file), verbose=0)

        while status != 2 and time < T:
            for model_name, model in base.items():
                if time < t * len(base):
                    # Build and solve
                    model.build()
                    result = model.solve(time_limit=t, tour=best_result.tour)
                else:
                    # Resume optimization
                    result = model.resume(time_limit=t, tour=best_result.tour)

                if best_result.objVal > result.objVal:
                    # If a better soluion is found, update the best result
                    best_result = result

                # Retrieve the result
                objVal = best_result.objVal
                if model_name in ['MIP', 'CP']:
                    status = status if status==2 else result.statistics['status']
                elif model_name == 'ALNS':
                    status = status if status==2 else 9
                    
                time += t

                if save_to_csv:
                    with open('rawdata_rnn_t{}_T{}.csv'.format(t, T), 'a') as f:
                        f.write(model_name + ',' + file.split('.')[0] + ',' + str(time) + ','
                                + str(objVal) + ',' + str(status) + '\n'
                        )


def make_raw_data(dir, delta_t=5, T=300, save_to_csv=True, model_name='MIP'):
    """
    Solve all the instances in 'dir' with the model ('model_name'), and
    record the performance at every 'delta_t' [sec] until it reaches optimality
    or 'T' [sec] passes.

    save_to_csv (bool): Save the record to csv if True.
    
    """
    if save_to_csv:
        with open('rawdata_{}_t{}_T{}.csv'.format(model_name, delta_t, T), 'a') as f:
            f.write('Model, Instance, t, objVal, Status' + '\n')

    for file in os.listdir(dir):
        if file in skip_list:
            continue
        print("file name: ", file)
        t = 0
        status = 9

        # Initialize the model
        if model_name == 'MIP':
            model = MIP(os.path.join(dir, file), verbose=0)
        if model_name == 'CP':
            model = CP(os.path.join(dir, file), verbose=0)
        if model_name == 'ALNS':
            model = ALNS_Agent(os.path.join(dir, file), verbose=0)

        while status != 2 and t < T:
            if t == 0:
                # Build and solve
                model.build()
                result = model.solve(time_limit=delta_t)
            else:
                # Resume optimization
                result = model.resume(time_limit=delta_t, tour=result.tour)

            # Retrieve the result
            objVal = result.objVal
            if model_name in ['MIP', 'CP']:
                solve_time = result.statistics['solve_time']
                status = result.statistics['status']
            elif model_name == 'ALNS':
                solve_time = delta_t
                status = 9

            t += delta_t if status != 2 else solve_time

            if save_to_csv:
                with open('rawdata_{}_t{}_T{}.csv'.format(model_name, delta_t, T), 'a') as f:
                    f.write(model_name + ',' + file.split('.')[0] + ',' + str(t) + ','
                            + str(objVal) + ',' + str(status) + '\n'
                    )

def make_dataset(delta_t, T, time_horizon=3, step=1):
    """
    step (int): determines the number of time-steps of the dataset.
                gets the data points at every delta_t * step seconds until the time limit is met.
    
    """
    
    num_algos = 3 # MIP, CP, ALNS

    csv_mip = open('rawdata_MIP_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_mip, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    mip_result = []
    for row in f:
        # row[1]: instance, [2]: time, [3]: objVal, [4]: status
        mip_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    csv_cp = open('rawdata_CP_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_cp, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    cp_result = []
    for row in f:
        cp_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    csv_alns = open('rawdata_ALNS_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_alns, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    alns_result = []
    for row in f:
        alns_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    raw_performance = {}
    ys = []

    X_raw = []
    m_2, c_2, a_2 = float('inf'), float('inf'), float('inf')

    m = mip_result.pop(0)
    c = cp_result.pop(0)
    a = alns_result.pop(0)
    while len(mip_result) > 0 or len(cp_result) > 0 or len(alns_result) > 0:
        X_raw.append((m[2], c[2], a[2]))

        # when all models reach 9 or T [sec] passed, move on to the next instance
        if (m[3] == 2 and c[3] == 2 and a[3] == 2) or (max(m[1], c[1], a[1]) > T-delta_t):
            raw_performance[m[0]] = X_raw

            #print("check: ", m[0], X_raw[-1], np.argmin(X_raw[-1]))
            y = np.argmin(X_raw[-1])
            if X_raw[-1].count(y) > 1: # multiple algorithms reached optimality
                y = np.argmin((m_2, c_2, a_2))
            ys.append(y)

            # Initialize temp variabls
            X_raw = []
            m_2, c_2, a_2 = float('inf'), float('inf'), float('inf')

            m = mip_result.pop(0)
            c = cp_result.pop(0)
            a = alns_result.pop(0)
        else:
            # if previous status is not 2, read the next line
            # if 2, keep the previous objVal
            # m_2, c_2, a_2 = time when it reached optimality
            if m[3] !=2: m = mip_result.pop(0)
            else: m_2 = min(m_2, m[1])

            if c[3] !=2: c = cp_result.pop(0)
            else: c_2 = min(c_2, c[1])

            if a[3] !=2: a = alns_result.pop(0)
            else: a_2 = min(a_2, a[1])
    
    raw_performance[m[0]] = X_raw

    #print("check: ", m[0], X_raw[-1], np.argmin(X_raw[-1]))
    y = np.argmin(X_raw[-1])
    if X_raw[-1].count(y) > 1: # multiple algorithms reached optimality
        y = np.argmin((m_2, c_2, a_2))
    ys.append(y)

    #for instance, y in zip(raw_performance, ys): 
    #    print(raw_performance[instance], y)

    # convert raw performance to performance metric 
    # (e.g., (3320, 3500, 3300) -> (behind, behind, best))
    performance = {}
    for instance in raw_performance:
        X = []
        for x_raw in raw_performance[instance]:
            X.append(tuple([int(x == min(x_raw)) for x in x_raw]))
        performance[instance] = X
    
    X_train = []
    y_train = []
    for i, instance in enumerate(performance):
        print(i, instance, ys[i])
        x_train = []
        for k, x in enumerate(performance[instance]):
            if len(x_train) < time_horizon * num_algos:
                if (k+1) % step == 0:
                    x_train.extend(x)
            else:
                X_train.append(copy(x_train))
                y_train.append(ys[i])

                # pop old data
                for j in range(num_algos):
                    x_train.pop(0)
    
    X_train = np.array(X_train)
    y_train = np.array(y_train)
    print(y_train)

    np.save('X_t{}_T{}_h{}.npy'.format(delta_t*step, T, time_horizon), X_train)
    np.save('y_t{}_T{}_h{}.npy'.format(delta_t*step, T, time_horizon), y_train)

    np.load('X_t{}_T{}_h{}.npy'.format(delta_t*step, T, time_horizon))
    np.load('y_t{}_T{}_h{}.npy'.format(delta_t*step, T, time_horizon))

    print("Dataset complete", X_train.shape, y_train.shape)


def make_dataset_rnn_switching_v2(t, T, time_horizon=3):
    """
    t (int)           : time interval when the performance is measured 
                        (used for detecting the raw data csv filename)
    T (int)           : total time
    time_horizon (int): number of time-steps used for prediction

    """
    
    num_algos = 3 # MIP, CP, ALNS

    csv_file = open('rawdata_rnn_t{}_T{}.csv'.format(t, T), "r")
    f = csv.reader(csv_file, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    mip_result = []
    cp_result = []
    alns_result = []
    for i, row in enumerate(f):
        if i % 3 == 0:
            # row[1]: instance, [2]: time, [3]: objVal, [4]: status
            mip_result.append((row[1], 
                            float(row[2]), 
                            float(row[3]), 
                            int(row[4]))
                        )
        if i % 3 == 1:
            # row[1]: instance, [2]: time, [3]: objVal, [4]: status
            cp_result.append((row[1], 
                            float(row[2]), 
                            float(row[3]), 
                            int(row[4]))
                        )
        if i % 3 == 2:
            # row[1]: instance, [2]: time, [3]: objVal, [4]: status
            alns_result.append((row[1], 
                            float(row[2]), 
                            float(row[3]), 
                            int(row[4]))
                        )
    ps_all = []
    ps = []
    best = float('inf')

    m = mip_result.pop(0)
    c = cp_result.pop(0)
    a = alns_result.pop(0)
    while len(mip_result) > 0 or len(cp_result) > 0 or len(alns_result) > 0:
        performance_prev = []
        performance = []

        performance_prev.append(best)
        if m[2] < best:
            best = m[2]
        performance.append(best)

        performance_prev.append(best)
        if c[2] < best:
            best = c[2]
        performance.append(best)

        performance_prev.append(best)
        if a[2] < best:
            best = a[2]
        performance.append(best)

        non_inf_max_prev = max([x for x in performance_prev if x != float('inf')])
        non_inf_max = max([x for x in performance if x != float('inf')])
        performance_prev = [x if x != float('inf') else non_inf_max_prev for x in performance_prev]
        performance = [x if x != float('inf') else non_inf_max for x in performance]

        p = [performance_prev[j]-performance[j] for j in range(len(performance))]
        ps.append(p)

        # if one method reached optimality or time limit, go to the next instance
        if (m[3] == 2 or c[3] == 2 or a[3] == 2) or (max(m[1], c[1], a[1]) > T-t):
            ps_all.append(ps)
            ps = []
            best = float('inf')

        m = mip_result.pop(0)
        c = cp_result.pop(0)
        a = alns_result.pop(0)

    print(ps_all)

    Xs = []
    ys = []
    for ps in ps_all:
        # If there is not enough data, skip the instance
        if len(ps)-time_horizon <= 0:
            continue

        for i in range(len(ps)-time_horizon):
            X = []
            for j in range(time_horizon):
                X.extend(ps[i+j])
            Xs.append(X)
            ys.append(ps[i+time_horizon])

    Xs = np.array(Xs)
    ys = np.array(ys)

    np.save('X_rnn_t{}_T{}_h{}.npy'.format(t, T, time_horizon), Xs)
    np.save('y_rnn_t{}_T{}_h{}.npy'.format(t, T, time_horizon), ys)

    np.load('X_rnn_t{}_T{}_h{}.npy'.format(t, T, time_horizon))
    np.load('y_rnn_t{}_T{}_h{}.npy'.format(t, T, time_horizon))

    print("Dataset complete", Xs.shape, ys.shape)


def make_dataset_rnn_switching(delta_t, T, time_horizon=3, t=20):
    """
    delta_t (int)     : time interval when the performance is measured 
                        (used for detecting the raw data csv filename)
    T (int)           : total time
    time_horizon (int): number of time-steps used for prediction
    t (int)           : time interval when rnn predicts the next cost improvement

    """

    assert (int(t/delta_t) - t/delta_t) < 0.00001, "t must be a multiple of delta_t"
    
    num_algos = 3 # MIP, CP, ALNS

    csv_mip = open('rawdata_MIP_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_mip, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    mip_result = []
    for row in f:
        # row[1]: instance, [2]: time, [3]: objVal, [4]: status
        mip_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    csv_cp = open('rawdata_CP_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_cp, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    cp_result = []
    for row in f:
        cp_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    csv_alns = open('rawdata_ALNS_t{}_T{}.csv'.format(delta_t, T), "r")
    f = csv.reader(csv_alns, delimiter=",", doublequote=True, lineterminator="\r\n", quotechar='"', skipinitialspace=True)
    next(f)
    alns_result = []
    for row in f:
        alns_result.append((row[1], 
                        float(row[2]), 
                        float(row[3]), 
                        int(row[4]))
                    )

    step = int(t / delta_t)    
    ps_all = []
    ps = []
    queue = [] # temp queue that stores part of objective func values

    m_2, c_2, a_2 = float('inf'), float('inf'), float('inf')
    m = mip_result.pop(0)
    c = cp_result.pop(0)
    a = alns_result.pop(0)
    non_nan_maxima = max([x for x in [m[2], c[2], a[2]] if x != float('inf')])
    while len(mip_result) > 0 or len(cp_result) > 0 or len(alns_result) > 0:
        # Add ith objective values to queue
        if len(queue) >= step + 1:
            queue.pop(0)
        item = [m[2], c[2], a[2]]
        print(m[0], item)
        queue.append([x if x != float('inf') else non_nan_maxima for x in item])

        # if queue is full, add cost improvement to ps
        if len(queue) == step + 1:
            cost_i = list(queue[0])
            cost_next = list(queue[-1])

            p = [cost_i[j]-cost_next[j] for j in range(len(cost_i))]
            ps.append(p)

        # if all the methods reached optimality or time limit, go to the next instance
        if (m[3] == 2 and c[3] == 2 and a[3] == 2) or (max(m[1], c[1], a[1]) > T-delta_t):
            ps_all.append(ps)

            m_2, c_2, a_2 = float('inf'), float('inf'), float('inf')
            m = mip_result.pop(0)
            c = cp_result.pop(0)
            a = alns_result.pop(0)
            non_nan_maxima = max([x for x in [m[2], c[2], a[2]] if x != float('inf')])
        else:
            if m[3] !=2: m = mip_result.pop(0)
            else: m_2 = min(m_2, m[1])

            if c[3] !=2: c = cp_result.pop(0)
            else: c_2 = min(c_2, c[1])

            if a[3] !=2: a = alns_result.pop(0)
            else: c_2 = min(a_2, c[1])
    
    print(ps)

    Xs = []
    ys = []
    for ps in ps_all:
        # If there is not enough data, skip the instance
        if len(ps)-step*time_horizon <= 0:
            continue

        for i in range(len(ps)-step*time_horizon):
            X = []
            for j in range(time_horizon):
                X.append(ps[i+step*j])
            Xs.append(X)
            ys.append(ps[i+step*time_horizon])

    Xs = np.array(Xs)
    ys = np.array(ys)

    np.save('X_rnn_delta{}_t{}_T{}_h{}.npy'.format(delta_t, t, T, time_horizon), Xs)
    np.save('y_rnn_delta{}_t{}_T{}_h{}.npy'.format(delta_t, t, T, time_horizon), ys)

    np.load('X_rnn_delta{}_t{}_T{}_h{}.npy'.format(delta_t, t, T, time_horizon))
    np.load('y_rnn_delta{}_t{}_T{}_h{}.npy'.format(delta_t, t, T, time_horizon))

    print("Dataset complete", Xs.shape, ys.shape)


if __name__ == "__main__":
    make_raw_data("train_instances_final", delta_t=5, T=300, model_name='MIP')
    make_raw_data("train_instances_final", delta_t=5, T=300, model_name='CP')
    make_raw_data("train_instances_final", delta_t=5, T=300, model_name='ALNS')
    make_dataset(delta_t=5, T=300, time_horizon=3, step=1)
    make_raw_data_rnn_switching("train_instances_final", t=20, T=300)
    make_dataset_rnn_switching_v2(t=20, T=300, time_horizon=3)
### ****
### Xian Lopez Alvarez
### 19/7/2017


import tensorflow as tf
import numpy as np
import tools
from data_loader import data_loader
import time
from params import NDIM_DISC, NDIM_CONT, category_names, category_paper_order
import sys


###########################################################################################################
### ****
def train(opts):
    # Parameter for discrete weights:
    ldisc_c = 1.2 / 10
    # Initialize array for discrete weights.
    ldisc_weights = np.zeros(NDIM_DISC, dtype=np.float32)
    
    # Create directory to store results:
    modelname, dircase = tools.prepare_dircase(opts)
    
    # Get all the parameters and variables of the network and its loss:
    graph = tf.get_default_graph()
    x_f                  = graph.get_tensor_by_name('x_f:0')
    x_b                  = graph.get_tensor_by_name('x_b:0')
    keep_prob            = graph.get_tensor_by_name('keep_prob:0')
    L_comb               = graph.get_tensor_by_name('L_comb:0')
    y_true_cont          = graph.get_tensor_by_name('y_true_cont:0')
    y_true_disc          = graph.get_tensor_by_name('y_true_disc:0')
    w_cont               = graph.get_tensor_by_name('w_cont:0')
    w_disc               = graph.get_tensor_by_name('w_disc:0')
    loss_disc_weights    = graph.get_tensor_by_name('loss_disc_weights:0')
    loss_cont_margin     = graph.get_tensor_by_name('loss_cont_margin:0')
    loss_cont_saturation = graph.get_tensor_by_name('loss_cont_saturation:0')
    
    # Load annotations:
    annotations_train = tools.load_annotations('train')
    annotations_val = tools.load_annotations('val')
    
    # Create data loaders:
    data_train = data_loader(annotations_train, opts)
    data_val = data_loader(annotations_val, opts)
    
    # Create optimzer:
    train_step = tf.train.AdamOptimizer(opts.initial_learning_rate).minimize(L_comb)
    
    # Lists for train and validations losses:
    train_loss_list = []
    val_loss_list = []
    batches_train = []
    batches_val = []
    train_metrics = []
    val_metrics = []
    
    # Start clock:
    start = time.time()
    
    with tf.Session() as sess:
        sess.run(tf.global_variables_initializer())
    
        # Create the saver:
        saver = tf.train.Saver()
        graph = tf.get_default_graph()
        
        # Save initial model:
        print('Saving model...')
        saver.save(sess, modelname, global_step=0)
        print('Done')
        
        # Main loop:
        batch_id = 0
        for i in range(opts.nsteps):
            batch_id = batch_id + 1
            
            if batch_id % opts.nsteps_print_batch_id == 0:
                print('batch %i / %i' % (i+1, opts.nsteps))
            
            # Load batch:
            im_full_prep_batch, im_body_prep_batch, true_labels_cont, true_labels_disc = data_train.load_batch_with_labels()
            
            # Compute weights:
            for cat_idx in range(NDIM_DISC):
                ldisc_weights[cat_idx] = 1. / np.log(ldisc_c + np.sum(true_labels_disc[:,cat_idx]))
            
            train_step.run(feed_dict={x_f: im_full_prep_batch,
                x_b: im_body_prep_batch,
                keep_prob: 0.5,
                y_true_cont: true_labels_cont,
                y_true_disc: true_labels_disc,
                w_cont: 1,
                w_disc: 1./6.,
                loss_disc_weights: ldisc_weights,
                loss_cont_margin: 0,
                loss_cont_saturation: 1500})
            
            # Loss and metrics in the current train batch:
            if batch_id % opts.nsteps_trainloss == 0:
                batches_train.append(batch_id)
                print('Doing evaluation on train set...')
                train_loss, _, mean_err, mean_ap = evaluate_on_dataset(sess, graph, data_train, opts)
                print('Train loss: %f' % train_loss)
                print('Train mean AP: ' + str(mean_ap))
                print('Train Mean Error: ' + str(mean_err))
                train_loss_list.append(train_loss)
                train_metrics.append([np.mean(mean_err), mean_ap])
    
            # Loss and metrics over the validation set:
            if batch_id % opts.nsteps_valloss == 0:
                batches_val.append(batch_id)
                print('Doing validation...')
                val_loss, _, mean_err, mean_ap = evaluate_on_dataset(sess, graph, data_val, opts)
                print('Validation loss: %f' % val_loss)
                print('Validation mean AP: ' + str(mean_ap))
                print('Validation Mean Error: ' + str(mean_err))
                val_loss_list.append(val_loss)
                val_metrics.append([np.mean(mean_err), mean_ap])
    
            # Save model:
            if batch_id % opts.nsteps_save == 0:
                print('Saving model...')
                saver.save(sess, modelname, global_step=batch_id)
                print('Done')
    
        # Validate the final model on the validation set:
        # (check we haven't saved already the last step)
        if opts.nsteps % opts.nsteps_valloss != 0:
            batches_val.append(batch_id)
            print('Doing validation...')
            val_loss, ap, mean_err, mean_ap = evaluate_on_dataset(sess, graph, data_val, opts)
            print('Validation loss: %f' % val_loss)
            print('Validation mean AP: ' + str(mean_ap))
            print('Validation Mean Error: ' + str(mean_err))
            val_loss_list.append(val_loss)
            val_metrics.append([np.mean(mean_err), mean_ap])
            # Show Avergae Precision for each class, in the same order as the paper:
            print('Validation AP:')
            for cat_idx in range(NDIM_DISC):
                print(category_names[category_paper_order[cat_idx] - 1] + ': ' + str(ap[category_paper_order[cat_idx] - 1] * 100))
        
        # Save the final model:
        # (check we haven't saved already the last step)
        if opts.nsteps % opts.nsteps_save != 0:
            print('Saving model...')
            saver.save(sess, modelname, global_step=opts.nsteps)
            print('Done')
    
    # Final time:
    end = time.time()
    print('-----------------------------------')
    print('Elapsed time: ' + str(end - start))
    
    # Plot results:
    if len(batches_train) > 0 and len(batches_val) > 1:
        train_metrics = np.asarray(train_metrics)
        val_metrics = np.asarray(val_metrics)
        metric_names = ['mean_mean_error', 'mean AP ']
        tools.plot_train(batches_train, batches_val, train_loss_list, val_loss_list, train_metrics, val_metrics, metric_names, dircase)


###########################################################################################################
### Compute metrics and loss on a dataset.
def get_cnn_var_dict(graph):
    
    var_dict = {
        'yc'                   : graph.get_tensor_by_name('yc:0'),
        'yd'                   : graph.get_tensor_by_name('yd:0'),
        'x_f'                  : graph.get_tensor_by_name('x_f:0'),
        'x_b'                  : graph.get_tensor_by_name('x_b:0'),
        'keep_prob'            : graph.get_tensor_by_name('keep_prob:0'),
        'L_comb'               : graph.get_tensor_by_name('L_comb:0'),
        'y_true_cont'          : graph.get_tensor_by_name('y_true_cont:0'),
        'y_true_disc'          : graph.get_tensor_by_name('y_true_disc:0'),
        'w_cont'               : graph.get_tensor_by_name('w_cont:0'),
        'w_disc'               : graph.get_tensor_by_name('w_disc:0'),
        'loss_disc_weights'    : graph.get_tensor_by_name('loss_disc_weights:0'),
        'loss_cont_margin'     : graph.get_tensor_by_name('loss_cont_margin:0'),
        'loss_cont_saturation' : graph.get_tensor_by_name('loss_cont_saturation:0')
    }
    
    return var_dict


###########################################################################################################
### Compute metrics and loss on a dataset.
def evaluate_on_dataset(sess, graph, data_loader, opts):
    
    yc                   = graph.get_tensor_by_name('yc:0')
    yd                   = graph.get_tensor_by_name('yd:0')
    x_f                  = graph.get_tensor_by_name('x_f:0')
    x_b                  = graph.get_tensor_by_name('x_b:0')
    keep_prob            = graph.get_tensor_by_name('keep_prob:0')
    L_comb               = graph.get_tensor_by_name('L_comb:0')
    y_true_cont          = graph.get_tensor_by_name('y_true_cont:0')
    y_true_disc          = graph.get_tensor_by_name('y_true_disc:0')
    w_cont               = graph.get_tensor_by_name('w_cont:0')
    w_disc               = graph.get_tensor_by_name('w_disc:0')
    loss_disc_weights    = graph.get_tensor_by_name('loss_disc_weights:0')
    loss_cont_margin     = graph.get_tensor_by_name('loss_cont_margin:0')
    loss_cont_saturation = graph.get_tensor_by_name('loss_cont_saturation:0')
    
    ldisc_c = 1.2 / 10
    ldisc_weights = np.zeros(26, dtype=np.float32)
    
    loss = 0
    y_cont_pred_concat = np.zeros((data_loader.n_images_per_epoch, NDIM_CONT), dtype=np.float32)
    y_disc_pred_concat = np.zeros((data_loader.n_images_per_epoch, NDIM_DISC), dtype=np.float32)
    y_cont_true_concat = np.zeros((data_loader.n_images_per_epoch, NDIM_CONT), dtype=np.float32)
    y_disc_true_concat = np.zeros((data_loader.n_images_per_epoch, NDIM_DISC), dtype=np.float32)
    
    progress = 0
    progress_step = 10
    print('0%...'),
    sys.stdout.flush()
    for batch_id in range(data_loader.n_batches_per_epoch):
        # Progress display:
        while progress + progress_step < np.float32(batch_id) / data_loader.n_batches_per_epoch * 100:
            progress = progress + progress_step
            print('%i%%...' % progress),
            sys.stdout.flush()
        
        # Load batch:
        im_full_batch, im_body_batch, true_labels_cont, true_labels_disc = \
            data_loader.load_batch_with_labels()
        # Compute weights:
        for cat_idx in range(26):
            ldisc_weights[cat_idx] = 1. / np.log(ldisc_c + np.sum(true_labels_disc[:,cat_idx]))
        # Run network:
        y_cont_pred, y_disc_pred, curr_loss = sess.run([yc, yd, L_comb], feed_dict={x_f: im_full_batch, 
            x_b: im_body_batch, 
            keep_prob: 1,
            y_true_cont: true_labels_cont,
            y_true_disc: true_labels_disc,
            w_cont: 1,
            w_disc: 1./6.,
            loss_disc_weights: ldisc_weights,
            loss_cont_margin: 0,
            loss_cont_saturation: 1500})
        # Accumulate loss:
        loss = loss + curr_loss
        # Concatenate predictions:
        y_cont_pred_concat[batch_id*opts.batch_size:(batch_id+1)*opts.batch_size, :] = y_cont_pred
        y_disc_pred_concat[batch_id*opts.batch_size:(batch_id+1)*opts.batch_size, :] = y_disc_pred
        y_cont_true_concat[batch_id*opts.batch_size:(batch_id+1)*opts.batch_size, :] = true_labels_cont
        y_disc_true_concat[batch_id*opts.batch_size:(batch_id+1)*opts.batch_size, :] = true_labels_disc
    print('100%')
    
    # Loss:
    loss = loss / data_loader.n_batches_per_epoch
    # Metrics:
    ap, mean_error = metrics_from_predictions(y_cont_pred_concat, y_disc_pred_concat, y_cont_true_concat, y_disc_true_concat)
    mean_ap = np.mean(ap)
    
    return loss, ap, mean_error, mean_ap


###########################################################################################################
### Compute Average Precision and Mean Error over a batch.
def metrics_from_predictions(y_cont_pred, y_disc_pred, y_cont_true, y_disc_true):
    
    # Compute Average Precision on each discrete category:
#    ap = np.zeros(NDIM_DISC, dtype=np.float32)
#    for cat_idx1 in range(NDIM_DISC):
#        if np.sum(y_disc_true[:, cat_idx1]) > 0:
#            ap[cat_idx1] = average_precision_score(y_disc_true[:, cat_idx1], y_disc_pred[:, cat_idx1])
#        else:
#            ap[cat_idx1] = -1
    
    ap = np.zeros(NDIM_DISC, dtype=np.float32)
    for cat_idx in range(NDIM_DISC):
        predictions = y_disc_pred[:, cat_idx]
        labels = y_disc_true[:, cat_idx]
        # Sort in descending order of confidence of the prediction:
        sorting_idxs = np.argsort(-predictions)
#        pred_sorted = predictions[sorting_idxs]
        labels_sorted = labels[sorting_idxs]
        # Number of real positives:
        n_real_pos = np.sum(labels)
        if n_real_pos < 1:
            tools.error('0 real positives in category ' + category_names[cat_idx])
        # True positives:
        # This array contains, at each position, the number of true positives that we would have with a threshold
        # that cut the observations at that point (for instance, position i of tp is the number of true positives
        # with a threshold that equal to the value of the i-th highest prediction, thus predicting exactly i
        # positives).
        tp = np.cumsum(labels_sorted)
        # Recall. The same as before, this is the recall with the threshold set at that position.
        recall = np.float32(tp) / n_real_pos
        # Precision:
        precision = np.float32(tp) / (np.arange(tp.shape[0]) + 1)
        # Average Precision computation:
        ap[cat_idx] = 0
        recallstep = 0.1
        for rec_limit in np.arange(0, 1+recallstep, recallstep):
            # Keep the thresholds for which the recall is bigger than rec_limit:
            mask = recall >= rec_limit
            if np.sum(mask) > 0:
                curr_prec = np.max(precision[mask])
            else:
                curr_prec = 0
            ap[cat_idx] = ap[cat_idx] + curr_prec
        # Finally divide by the number of discretization points:
        recallpoints = len(np.arange(0, 1+recallstep, recallstep))
        ap[cat_idx] = ap[cat_idx] / recallpoints
    
    # Compute Mean Error on each continuous variable:
#    error_rates = np.zeros(NDIM_CONT, dtype=np.float32)
#    for var_idx in range(NDIM_CONT):
#        abs_dif = np.abs(y_cont_true[:, var_idx] - y_cont_pred[:, var_idx])
#        error_rates[var_idx] = np.mean(abs_dif)
    error_rates = np.zeros(NDIM_CONT, dtype=np.float32)
    for var_idx in range(NDIM_CONT):
        abs_sq = np.square(y_cont_true[:, var_idx] - y_cont_pred[:, var_idx])
        error_rates[var_idx] = np.sqrt(np.mean(abs_sq))
    
    return ap, error_rates


###########################################################################################################
### Evaluate a given model in all datasets
def evaluate_model(opts):
    
    # Load annotations:
    annotations_train = tools.load_annotations('train')
    annotations_val = tools.load_annotations('val')
    annotations_test = tools.load_annotations('test')
    
    # Create data loaders:
    data_train = data_loader(annotations_train, opts)
    data_val = data_loader(annotations_val, opts)
    data_test = data_loader(annotations_test, opts)
    
    # Start clock:
    start = time.time()
    
    with tf.Session(config=tools.config) as sess:
        # Initialize variables:
        sess.run(tf.global_variables_initializer())
        
        # Get the graph:
        graph = tf.get_default_graph()
    
        # Loss and metrics over the train set:
        print('')
        print('Evaluating on train set...')
        loss_train, _, mean_error_train, mean_ap_train = evaluate_on_dataset(sess, graph, data_train, opts)
        print('Train loss: %f' % loss_train)
        print('Train mean AP: ' + str(mean_ap_train))
        print('Train Mean Error: ' + str(mean_error_train))
    
        # Loss and metrics over the validation set:
        print('')
        print('Evaluating on validation set...')
        loss_val, _, mean_error_val, mean_ap_val = evaluate_on_dataset(sess, graph, data_val, opts)
        print('Validation loss: %f' % loss_val)
        print('Validation mean AP: ' + str(mean_ap_val))
        print('Validation Mean Error: ' + str(mean_error_val))
    
        # Loss and metrics over the test set:
        print('')
        print('Evaluating on test set...')
        loss_test, ap_test, mean_error_test, mean_ap_test = evaluate_on_dataset(sess, graph, data_test, opts)
        print('Test loss: %f' % loss_test)
        print('Test mean AP: ' + str(mean_ap_test))
        print('Test Mean Error: ' + str(mean_error_test))
    
    # Show Avergae Precision for each class, in the same order as the paper:
    print('Test AP:')
    for cat_idx in range(NDIM_DISC):
        print(category_names[category_paper_order[cat_idx] - 1] + ': ' + str(ap_test[category_paper_order[cat_idx] - 1] * 100))
    
    # Final time:
    end = time.time()
    print('-----------------------------------')
    print('Elapsed time: ' + str(end - start))

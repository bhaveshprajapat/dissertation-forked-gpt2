#!/usr/bin/env python3

import os
import sys
sys.path += [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src')]
sys.path += [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))]

import fire
import json
import os
import numpy as np
import tensorflow as tf
import tflex

import model, sample, encoder

def interact_model(
    model_name='117M',
    restore_from=None,
    seed=None,
    nsamples=1,
    batch_size=1,
    length=None,
    temperature=1,
    top_k=0,
    top_p=0.0,
    penalize=0,
    prompt=None,
    checkpoint_dir='checkpoint'
):
    """
    Interactively run the model
    :model_name=117M : String, which model to use
    :seed=None : Integer seed for random number generators, fix seed to reproduce
     results
    :nsamples=1 : Number of samples to return total
    :batch_size=1 : Number of batches (only affects speed/memory).  Must divide nsamples.
    :length=None : Number of tokens in generated text, if None (default), is
     determined by model hyperparameters
    :temperature=1 : Float value controlling randomness in boltzmann
     distribution. Lower temperature results in less random completions. As the
     temperature approaches zero, the model will become deterministic and
     repetitive. Higher temperature results in more random completions.
    :top_k=0 : Integer value controlling diversity. 1 means only 1 word is
     considered for each step (token), resulting in deterministic completions,
     while 40 means 40 words are considered at each step. 0 (default) is a
     special setting meaning no restrictions. 40 generally is a good value.
    :top_p=0.0 : Float value controlling diversity. Implements nucleus sampling,
     overriding top_k if set to a value > 0. A good setting is 0.9.
    :penalize=0.0 : Float value controlling "used" penalty. Implements repetition
     reduction (similar to CTRL) if set to a value > 0. A decent setting might be 0.85
     with temperature 0.3 and top_k 40.
    """
    if batch_size is None:
        batch_size = 1
    assert nsamples % batch_size == 0

    enc = encoder.get_encoder(model_name)
    hparams = model.default_hparams()
    with open(os.path.join('models', model_name, 'hparams.json')) as f:
        hparams.override_from_dict(json.load(f))

    if length is None:
        length = hparams.n_ctx // 2
    elif length > hparams.n_ctx:
        raise ValueError("Can't get samples longer than window size: %s" % hparams.n_ctx)

    with tflex.Session(graph=tf.Graph()) as sess:
        context = tf.placeholder(tf.int32, [batch_size, None])
        np.random.seed(seed)
        tf.set_random_seed(seed)
        output = sample.sample_sequence(
            hparams=hparams, length=length,
            context=context,
            batch_size=batch_size,
            temperature=temperature, top_k=top_k, top_p=top_p, penalize=penalize
        )

        saver = tflex.Saver()
        if restore_from is None:
          restore_from = os.path.join('models', model_name)
        ckpt = tflex.latest_checkpoint(restore_from)
        saver.restore(sess, ckpt)

        while True:
            if prompt is not None:
              if os.path.isfile(prompt):
                  with open(prompt) as f:
                      raw_text = f.read()
              else:
                  raw_text = prompt
            else:
                raw_text = input("Model prompt >>> ")
                if not raw_text:
                    raw_text="\n"
            if len(raw_text) > 1 and raw_text.endswith('\n'):
                raw_text = raw_text[:-1]
            print('Prompt:', repr(raw_text))
            context_tokens = enc.encode(raw_text)
            generated = 0
            for _ in range(nsamples // batch_size):
                out = sess.run(output, feed_dict={
                    context: [context_tokens for _ in range(batch_size)]
                })[:, len(context_tokens):]
                for i in range(batch_size):
                    generated += 1
                    text = enc.decode(out[i])
                    print("=" * 40 + " SAMPLE " + str(generated) + " " + "=" * 40)
                    sys.stdout.write(raw_text)
                    print(text)
                    sys.stdout.flush()
            print("=" * 80)

if __name__ == '__main__':
    fire.Fire(interact_model)

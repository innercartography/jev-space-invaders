"""UFA arena: one instrumented loop for comparing Space Invaders decision policies.

    environment -> extract -> representation -> policy (decider) -> action -> environment
                                                         +-> trace -> results / compare

Each stage is its own module and is chosen by name in an experiment config, so
one dimension can change while the seeds and everything else stay fixed.
"""

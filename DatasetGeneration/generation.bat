:: Useful commands:
:: cd <directory>
:: copy path\to\file destination\path
:: xcopy path\to\dirs destination\path /E
:: rmdir "<dir_name>" /s /q
:: ren path\to\file <name>
:: del /F /Q path\to\file 

:: Options:
:: n_procedures=<integer>
:: pd_variant=[im, ilp]

set n_procedures=10
set n_norm_traces=100
set n_anom_traces=400
set n_dataset_replicas=5
set training_test_percentage=0.25

call clean_environment
python dataset_generation.py %n_procedures% %n_norm_traces% %n_anom_traces% %n_dataset_replicas% %training_test_percentage%





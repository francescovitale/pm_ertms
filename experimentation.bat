:: Useful commands:
:: cd <directory>
:: copy path\to\file destination\path
:: xcopy path\to\dirs destination\path /E
:: rmdir "<dir_name>" /s /q
:: ren path\to\file <name>
:: del /F /Q path\to\file 

:: Options:
:: n_dataset_replicas=<integer>
:: pd_variant=[im, ilp]

set n_dataset_replicas=4
set pd_variant=ilp25

for /l %%a in (0, 1, %n_dataset_replicas%) do (

	mkdir Results\%%a

	call clean_environment
	copy Data\EventLogs\%%a\BehaviorCharacterization\EL.xes Input\BC
	xcopy Data\EventLogs\%%a\OnlineBehavior Input\OB\EventLogs /E

	python behavior_characterization.py %pd_variant%
	copy Output\BC\PN.pnml Input\OB\PetriNet
	
	python online_behavior_diagnosis.py
	
	xcopy Output\OB\Diagnoses Results\%%a /E

	
)





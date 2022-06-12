## Dataset
Contains 
* the compressed dataset used to train the proof-of-concept prototype

### Naming Convention
Each sample of the dataset is stored in an individual .csv file and conforms with the following naming convention:
```
<participant>_<gesture>_<condition>_<repetition>_cut.csv
```
E. g., the file named P1_tap_demonstrator_1_cut.csv contains the data of the first Tap sample of participant P1 performed on the demonstrator. The data is
stored in the following format:
```
1: Time (sec), Resistance, Capacitance, Baseline (Resistance), Baseline (Capacitance)
2: 0.0, <res.#1>, <cap.#1>, <res. baseline>, <cap. baseline>
3 - X: ...
X + 1: <end time>, <res.#X>, <cap.#X>, <res. baseline>, <cap. baseline>
 '''

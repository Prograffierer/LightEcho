// fuer Arduino 1 muss der zweite Block auskommentiert sein und der erste aktiv,
// fuer Arduino 2 andersrum

unsigned int pins[] = {A0, A1, A2, A3, A4, A5};
int field[] = {0, 1, 2, 3, 4, 5};
unsigned int led[] = {3, 5, 6, 9, 10, 11};
int s = 6;
bool controlsRGB = false;

/*
unsigned int pins[] = {A0, A1, A2};
int field[] = {6, 7, 8};
unsigned int led[] = {3, 5, 6};
int s = 3;
bool controlsRGB = true;
*/

int activeField = -1;
int R[] = {255, 255, 178, 0, 0, 0, 0, 178, 255};
int G[] = {0, 178, 255, 255, 255, 178, 0, 0, 0};
int B[] = {0, 0, 0, 0, 178, 255, 255, 255, 178};

void setup() {
  Serial.begin(9600);
  Serial.setTimeout(5000);
  for (int i = 0; i < s; i++){
    pinMode(pins[i], INPUT_PULLUP);
  }
  for (int i = 0; i < s; i++){
    pinMode(led[i], OUTPUT);
  }
  pinMode(13, OUTPUT);
}

void set_color_for_cmd(int cmd) {
  if (controlsRGB){
    if (cmd < 9) {
      analogWrite(9, R[cmd]);
      analogWrite(10, G[cmd]);
      analogWrite(11, B[cmd]);
    } else if (cmd == 9) {
      analogWrite(9, 0);
      analogWrite(10, 255);
      analogWrite(11, 0);
    } else if (cmd == 10) {
      analogWrite(9, 255);
      analogWrite(10, 0);
      analogWrite(11, 0);
    }
  }
}

void set_val_for_all_led(int val) {
  for (int i=0; i<s; i++) {
    digitalWrite(led[i], val);
  }
}

void execute_cmd(int cmd) {
  set_color_for_cmd(cmd);
  if (cmd < 9) {
    set_val_for_all_led(LOW);
    for (int i=0; i<s; i++) {
      if (field[i] == cmd){
        digitalWrite(led[i], HIGH);
      }
    }
  } else if ((cmd == 9) || (cmd == 10)) {
    set_val_for_all_led(HIGH);
    delay(1000);
    set_val_for_all_led(LOW);
  } else {
    set_val_for_all_led(LOW);
  }
}

void loop() {
  int i;
  unsigned int max_f = 0;
  unsigned int max_val = 0;
  unsigned long start_time = 0;
  int foundSth = 0;
  digitalWrite(13, HIGH);
  while (foundSth == 0){
    for (int j = 0; (j < 20) && (foundSth == 0); j++){
      for (i = 0; i < s; i++){
        int p = pins[i];
        int f = field[i];
        int val = analogRead(p);
        if ((f != activeField) && (val < 600)){
          if (start_time == 0){
            start_time = millis();
          }
          if (val > max_val){
            max_val = val;
            max_f = f;
          }
        }
      }
      if ((start_time > 0) && (millis() - start_time > 200)){
        digitalWrite(13, LOW);
        unsigned int code = max_f << 12 + max_val << 2;
        while (Serial.available() > 0){Serial.read();}
        Serial.write(max_f);
        Serial.write(max_val / 4);
        unsigned long timeout_start = millis();
        while ((Serial.available() == 0) && (millis() - timeout_start < 2000)){}
        activeField = Serial.read();
        execute_cmd(activeField);
        foundSth = 1;
      }
    }
    if (Serial.available() > 0){
      activeField = Serial.read();
      execute_cmd(activeField);
    }
  }
}

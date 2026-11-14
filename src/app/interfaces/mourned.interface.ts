// The favorite the chapter before carried, dead since, off the death register: what his stone shows above the obituary that opens the chapter.
export interface Mourned {
  age: number;
  at: string; // the tile he fell on, `x,y`
  born: number; // the year he appeared; the year he died is his registry entry's
  cause: string; // the death register's, a `DEATH_CAUSES` key save the few the panel files under « other »
  epitaph?: string; // the chronicler's line, absent until written
  id: number;
  killer?: string; // his slayer's name, absent where nobody struck: age, hunger, a fall
  name: string;
}

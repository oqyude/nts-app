# NTS Excel Calculator

This project reproduces the Excel calculations in pure Python, without any Excel dependency.

## Setup

No third-party dependencies are required.

## Run

```bash
python main.py
```

To use your own input values, provide a JSON file:

```bash
python main.py --input input.json
```

To also export results as JSON:

```bash
python main.py --json result.json
```

## JSON Input Format

```json
{
  "experiments": [
    {
      "idx": 1,
      "delta1": -1,
      "delta2": -1,
      "x1": 43.75,
      "x2": 43.75,
      "x3": 12.5,
      "y1": 1167,
      "y2": 1238,
      "y3": 963
    },
    {
      "idx": 2,
      "delta1": -1,
      "delta2": 1,
      "x1": 35,
      "x2": 35,
      "x3": 30,
      "y1": 991,
      "y2": 992,
      "y3": 849
    },
    {
      "idx": 3,
      "delta1": 1,
      "delta2": -1,
      "x1": 55,
      "x2": 34.97,
      "x3": 10,
      "y1": 1167,
      "y2": 1116,
      "y3": 1135
    },
    {
      "idx": 4,
      "delta1": 1,
      "delta2": 1,
      "x1": 45.83,
      "x2": 25.17,
      "x3": 25,
      "y1": 967,
      "y2": 1119,
      "y3": 1058
    }
  ],
  "g_crit": 0.7679,
  "t_crit": 2.306,
  "f_crit": 239
}
```

# Modeling HSE daily trolly data 
Project exploring the HSE Emergency Care Report Trolley data. Current aim is to fit autoregressive models for exploration. Long term goals involve applying a bayesian ranking model such as in [this paper](http://arxiv.org/abs/2510.14723). 
Note: Currently the organization of the repo is a bit of a mess.

![Our poster presentation](./Poster/Poster_Presentation.png "Poster 2026/02/04")
## Exploratory analysis
* Using bayes/rJAGS: AR(1) model of weekly rate (per 10,000 people) with an annual cycle component
## Data sources
* [Emergency care report](https://www2.hse.ie/services/urgent-emergency-care-report/)
* [Health region populations](https://data.cso.ie/)
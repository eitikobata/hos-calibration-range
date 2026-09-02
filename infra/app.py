#!/usr/bin/env python3
import aws_cdk as cdk

from infra.hos_stack import HosCalibrationStack

app = cdk.App()
HosCalibrationStack(app, "HosCalibrationRange")
app.synth()

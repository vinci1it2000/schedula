import React from "react";

import Box from '@mui/material/Box';
import Stepper from '@mui/material/Stepper';
import Step from '@mui/material/Step';
import StepLabel from '@mui/material/StepLabel';
import Button from '@mui/material/Button';


export default function _stepper(props) {
    const [activeStep, setActiveStep] = React.useState(0);

    const handleNext = () => {
        setActiveStep(activeStep + 1);
    };

    const handleBack = () => {
        setActiveStep(activeStep - 1);
    };

    const handleStep = (step) => {
        setActiveStep(step);
    };
    return (
        <React.Fragment>
            <Box sx={{
                display: 'flex',
                justifyContent: "flex-start",
                alignItems: "baseline",
                pt: 1, pb: 3
            }}>
                <Button key="back"
                        variant="contained"
                        onClick={handleBack}
                        disabled={activeStep === 0}>
                    Back
                </Button>
                <Stepper key="stepper" activeStep={activeStep}
                         sx={{flexGrow: 1}}
                         alternativeLabel nonLinear>
                    {props.children.map((element, index) => (
                        <Step onClick={handleStep.bind(null, index)}
                              key={index}
                              style={{cursor: 'pointer'}}>
                            <StepLabel>{element.props.schema.title}</StepLabel>
                        </Step>
                    ))}
                </Stepper>
                <Button key="next"
                        variant="contained"
                        onClick={handleNext}
                        disabled={activeStep === props.children.length - 1}
                >
                    Next
                </Button>
            </Box>
            <React.Fragment>
                {props.children[activeStep]}
            </React.Fragment>
        </React.Fragment>
    );
}
import React, {Suspense} from "react";

const Box = React.lazy(() => import('@mui/material/Box'));
const Stepper = React.lazy(() => import('@mui/material/Stepper'));
const Step = React.lazy(() => import('@mui/material/Step'));
const StepLabel = React.lazy(() => import('@mui/material/StepLabel'));
const Button = React.lazy(() => import('@mui/material/Button'));


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
    let elements = (props.elements || {});
    return (
        <Suspense>
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
                              style={{cursor: 'pointer'}} {...(elements[index] || {}).props}>
                            <StepLabel>{(elements[(element.props || {}).index] || {}).name || ((element.props || {}).schema || {}).title || (element.props || {}).name}</StepLabel>
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
        </Suspense>
    );
}
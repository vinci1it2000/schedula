import schedula as sh

from models.imperial import imperial
from models.metric import metric

converter = sh.BlueDispatcher(name='LengthConverter')
converter.extend(imperial, metric)  # Concatenate imperial and metric models.

# Add the connection between the two unit system.
converter.add_function(
    'inch2cm', lambda inch: 2.54 * inch, ['in'], ['cm'],
    description='Converts inches to cm.'
)
converter.add_function(
    'cm2inch', lambda cm: cm / 2.54, ['cm'], ['in'],
    description='Converts cm to inches.'
)

if __name__ == '__main__':
    converter.register().plot(
        graph_attr={'ratio': '0.5'}, engine='neato', body={'style': 'filled'},
        index=True
    )

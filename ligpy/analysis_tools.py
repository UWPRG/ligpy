"""
Tools used by the `explore_ligpy_results.ipynb` notebook that help with
analysis and plotting.
"""
import os

import cPickle as pickle
import numpy as np

from constants import MW


def load_results(path):
    """
    Load the results from the ODE solver, along with the program parameters
    used to generate those results.  The program parameters should be saved
    in the `prog_params.pkl` file generated by `ligpy.py`.  The model species
    concentration results should be in the same format as those output by
    DDASAC (see the ligpy/sample_files/ folder for an example).

    Parameters
    ----------
    path  : str
            path to the folder that contains `/results_dir/`, where the *.out
            files (model results) and `prog_params.pkl` are saved.

    Returns
    -------
    end_time         : float
                       the pyrolysis end time in seconds (excludes cool-down
                       time)
    output_time_step : float
                       the time step at which results were saved (sec)
    initial_T        : float
                       initial temperature (K)
    heating_rate     : float
                       the heating rate (K/min)
    max_T            : float
                       maximum temperature of pyrolysis (K)
    atol             : float
                       absolute tolerance used by the ODE solver
    rtol             : float
                       relative tolerance used by the ODE solver
    plant            : str
                       the name of the lignin species modeled
    cool_time        : int
                       the time (s) to cool down after an isothermal hold
    y                : numpy matrix
                       a matrix with the concentrations of each species in the
                       kinetic scheme for every time in `t` (mol/L)
    t                : numpy array
                       array with all the times (s) corresponding to entries in
                       `y` and `T`
    T                : numpy array
                       array with the temperature (K) at every time in `t`
    specieslist      : list
                       a list of all the species participating in the model
    speciesindices   : dict
                       dictionary where species names are keys and values are
                       the index in `y` that corresponds to that species
    indices_to_species : dict
                         the opposite of speciesindices


    """
    rpath = path + '/results_dir'
    if not os.path.exists(rpath):
        raise ValueError('Please specify a valid directory with a'
                         ' results_dir folder.')
    with open(rpath + '/prog_params.pkl', 'rb') as params:
        prog_params = pickle.load(params)

    end_time = prog_params[0]
    output_time_step = prog_params[1]
    initial_T = prog_params[2]
    heating_rate = prog_params[3]
    max_T = prog_params[4]
    atol = prog_params[5]
    rtol = prog_params[6]
    plant = prog_params[7]
    cool_time = prog_params[8]

    if not os.path.isfile(rpath + '/ddasac_results_1.out'):
        raise IOError('There is not a valid DDASAC .out file.')

    # Determine the order that species are listed in the DDASAC model.c file
    with open(path + '/model.c', 'rb') as modelc:
        body = modelc.read()
        spos = body.find('enum {')
        modelc.seek(spos+6)
        # this includes the species list that I want to find
        listiwant = modelc.read(1000)
        # this is the list of all the species in the DDASAC model
        species_ddasac = ''
        for i, char in enumerate(listiwant):
            if char == '}':
                species_ddasac = listiwant[:i]
                break

    # Build a list of species from this string of species
    species_ddasac = species_ddasac.replace('\n', '').replace(' ', '')
    specieslist_ddasac = []
    for s in species_ddasac.split(','):
        specieslist_ddasac.append(s)

    # Build dictionaries of corresponding indices (these indices from DDASAC's
    # output are different from those from `ligpy_utils.get_speciesindices()`)
    speciesindices_ddasac = {}
    for i, species in enumerate(specieslist_ddasac):
        speciesindices_ddasac[species] = i
    indices_to_species_ddasac = dict(zip(speciesindices_ddasac.values(),
                                         speciesindices_ddasac.keys()))
    # Sort to make sure legends will always be the same
    specieslist_ddasac.sort()

    # Read the first DDASAC results file
    file1 = rpath + '/ddasac_results_1.out'
    t, y, T = read_results_files(file1, specieslist_ddasac)
    # Check to see if a temperature ramp was followed by an isothermal stage
    try:
        file2 = rpath + '/ddasac_results_2.out'
        t2, y2, T2 = read_results_files(file2, specieslist_ddasac)
        y = np.concatenate((y, y2[1:]))
        t = np.concatenate((t, t[-1]+t2[1:]))
        T = np.concatenate((T, T2[1:]))
    except IOError:
        print 'There is not a second DDASAC results file (isothermal hold)'
    # Check to see if a cool down phase was included
    try:
        file3 = rpath + '/ddasac_results_3.out'
        t3, y3, T3 = read_results_files(file3, specieslist_ddasac)
        y = np.concatenate((y, y3[1:]))
        t = np.concatenate((t, t[-1]+t3[1:]))
        T = np.concatenate((T, T3[1:]))
    except IOError:
        print 'There is not a third DDASAC results file (cool down period)'

    return [end_time, output_time_step, initial_T, heating_rate, max_T, atol,
            rtol, plant, cool_time, y, t, T, specieslist_ddasac,
            speciesindices_ddasac, indices_to_species_ddasac]


def read_results_files(filename, specieslist_ddasac):
    """
    Read and process the DDASAC *.out results files so they can be
    combined.

    Parameters
    ----------
    filename           : str
                         the filename of the *.out file (including relative
                         or absolute path)
    specieslist_ddasac : list
                         the specieslist_ddasac object from load_results()

    Returns
    -------
    t : numpy array
        an array with the output time (s) for each entry in the
        concentration or temperature arrays
    y : numpy matrix
        a matrix with the concentrations of each species in the model for
        every timepoint in `t` (mol/L)
    T : numpy array
        an array with the temperature at evey timepoint in `
    """
    with open(filename, 'r') as result:
        # There are 6 lines of descriptive text at the end of file
        num_lines = sum(1 for line in result) - 7
        t = np.zeros((num_lines, 1), dtype='float64')
        T = np.zeros((num_lines, 1), dtype='float64')
        y = np.zeros((num_lines, len(specieslist_ddasac)), dtype='float64')

    with open(filename, 'r') as result:
        for i, line in enumerate(result.readlines()):
            if 1 <= i < num_lines + 1:
                t[i-1] = line.split('\t')[0].split(' ')[1]
                T[i-1] = line.split('\t')[-2]
                for j, concentration in enumerate(line.split('\t')[1:-2]):
                    y[i-1, j] = concentration

    return t, y, T


def tar_elem_analysis(speciesindices, y, t, t_choice='end'):
    """
    Calculate the elemental analysis of the tar fraction at a specified time
    (moles of C, H, O). The species that make up the tar fraction are specified
    in the MW dictionary (in `constants.py`).  This function also returns the
    wt% and mol% of C, H, O at that specified time.

    Parameters
    ----------
    speciesindices : dict
                     dictionary from `load_results()` where species names are
                     keys and values are the index in `y` that corresponds to
                     that species
    y              : numpy array
                     a matrix with the concentrations of each species in the
                     kinetic scheme for every time in `t` (mol/L)
    t              : numpy array
                     array with all the times (s) corresponding to entries in
                     `y` and `T`
    t_choice       : str or int, optional
                     if 'end' (default) then this elemental analysis will be
                     done at the last timepoint saved in the simulation (i.e.
                     after any isothermal or cool-down stage).  Otherwise, an
                     integer specifying the index of the `t` array can be
                     passed to do the analysis at a specified time.

    Returns
    -------
    ea0            : numpy array
                     the elemental analysis at time = 0
    ea             : numpy array
                     the elemental analysis of tars at the specified time
    ea0_molpercent : numpy array
                     the mole% of C, H, O at time = 0
    ea_molpercent  : numpy array
                     the mole% of C, H, O at the specified time
    ea0_wtpercent  : numpy array
                     the wt% of C, H, O at time = 0
    ea_wtpercent   : numpy array
                     the wt% of C, H, O at the specified time
    choice         : str
                     a string describing the time that was chosen for analysis
    t_index        : int
                     the index of the time array at which analysis was done
    """
    # Calculate the elemental analysis at time=0
    ea0 = np.zeros(3)
    for species in MW:
        if y[0, speciesindices[species]] != 0:
            # mol C/L, mol H/L, mol O/L
            # NOTE: in MW dict, only PLIGH, PLIGO, PLIGC contribute to ea0
            ea0[0] += y[0, speciesindices[species]] * MW[species][3][0]
            ea0[1] += y[0, speciesindices[species]] * MW[species][3][1]
            ea0[2] += y[0, speciesindices[species]] * MW[species][3][2]

    # Calculate the elemental analysis at some later time
    if t_choice == 'end':
        t_index = len(t) - 1
        choice = 'Analysis done at the end of the entire simulation.'
    else:
        t_index = t_choice
        choice = 'Analysis done at time = %s sec.' % t[t_index]

    ea = np.zeros(3)
    for species in MW:
        if MW[species][1] in set(['t', 'lt', 'H2O']):
            # mol C,H,O/L
            ea[0] += y[t_index, speciesindices[species]] * MW[species][3][0]
            ea[1] += y[t_index, speciesindices[species]] * MW[species][3][1]
            ea[2] += y[t_index, speciesindices[species]] * MW[species][3][2]

    ea0_molpercent = ea0 / ea0.sum()
    ea_molpercent = ea / ea.sum()
    # Convert to g/L for calculating wt%
    ea_g = ea * [12.011, 1.0079, 15.999]
    ea0_g = ea0 * [12.011, 1.0079, 15.999]
    ea_wtpercent = ea_g / ea_g.sum()
    ea0_wtpercent = ea0_g / ea0_g.sum()

    return (ea0, ea, ea0_molpercent, ea_molpercent, ea0_wtpercent,
            ea_wtpercent, choice, t_index)


def C_fun_gen(fractions, speciesindices, y, time):
    """
    Calculate the distribution of carbon functional groups as a percent of
    total carbon.

    Parameters
    -----------
    fractions      : list
                     The lumped phases that you want to include (as specified
                     in MW['species'][1], options are any subset of
                     ['g','s','lt','t','char','H20','CO','CO2'] or ['initial']
                     for the case when you want to determine the initial
                     distribution before pyrolysis)
    speciesindices : dict
                     dictionary from `load_results()` where species names are
                     keys and values are the index in `y` that corresponds to
                     that species
    y              : numpy array
                     a matrix with the concentrations of each species in the
                     kinetic scheme for every time in `t` (mol/L)
    time           : int
                     the index of the timepoint that you want the results for

    Returns
    -------
    C_fun : numpy array
            the distribution of carbon functional groups as a percent of total
            carbon.  The order of the elements in the array is:
            carbonyl, aromatic C-O, aromatic C-C, aromatic C-H, aliphatic C-O,
            aromatic methoxyl, aliphatic C-C
    """
    C_fun = np.zeros(7)
    ind = speciesindices
    for species in MW:
        if fractions == ['initial']:
            time = 0
            if y[time, speciesindices[species]] != 0:
                # moles of functional group/L (order from Return docstring)
                C_fun[0] += y[time, ind[species]] * MW[species][4][0]
                C_fun[1] += y[time, ind[species]] * MW[species][4][1]
                C_fun[2] += y[time, ind[species]] * MW[species][4][2]
                C_fun[3] += y[time, ind[species]] * MW[species][4][3]
                C_fun[4] += y[time, ind[species]] * MW[species][4][4]
                C_fun[5] += y[time, ind[species]] * MW[species][4][5]
                C_fun[6] += y[time, ind[species]] * MW[species][4][6]
        else:
            if MW[species][1] in set(fractions):
                C_fun[0] += y[time, ind[species]] * MW[species][4][0]
                C_fun[1] += y[time, ind[species]] * MW[species][4][1]
                C_fun[2] += y[time, ind[species]] * MW[species][4][2]
                C_fun[3] += y[time, ind[species]] * MW[species][4][3]
                C_fun[4] += y[time, ind[species]] * MW[species][4][4]
                C_fun[5] += y[time, ind[species]] * MW[species][4][5]
                C_fun[6] += y[time, ind[species]] * MW[species][4][6]
    C_fun /= C_fun.sum()

    return C_fun


def lump_species(speciesindices, m):
    """
    Lump the molecular species in the model into subsets of
    solids, tars, and gases. Also separate heavy tars into
    phenolic and syringol families.

    Parameters
    ----------
    speciesindices : dict
                     dictionary from `load_results()` where species names are
                     keys and values are the index in `y` that corresponds to
                     that species
    m              : numpy array
                     a matrix with the mass fraction of each species in the
                     kinetic scheme for every time in `t`

    Returns
    -------
    lumped            : numpy array
                        each row in this array is the mass fraction of a
                        lumped phase (0 = solid, 1 = heavy tar, 2 = light tar,
                        3 = gas, 4 = CO, 5 = CO2, 6 = H2O, 7 = char)
    phenolic_families : numpy array
                        Splits the heavy tar components into the phenol
                        family (first row) and syringol family (second row)
    morelumped        : numpy array
                        a "more lumped" version of `lumped` where
                        column 0 = solids, 1 = tars, 2 = gases
    """
    lumped = np.zeros((m.shape[0], 8))
    phenolic_families = np.zeros((m.shape[0], 2))
    for species in MW:
        if MW[species][1] == 's':
            lumped[:, 0] += m[:, speciesindices[species]]
        elif MW[species][1] == 't':
            lumped[:, 1] += m[:, speciesindices[species]]
            if MW[species][2] == 'p':
                phenolic_families[:, 0] += m[:, speciesindices[species]]
            elif MW[species][2] == 's':
                phenolic_families[:, 1] += m[:, speciesindices[species]]
        elif MW[species][1] == 'lt':
            lumped[:, 2] += m[:, speciesindices[species]]
        elif MW[species][1] == 'g':
            lumped[:, 3] += m[:, speciesindices[species]]
        elif MW[species][1] == 'CO':
            lumped[:, 4] += m[:, speciesindices[species]]
        elif MW[species][1] == 'CO2':
            lumped[:, 5] += m[:, speciesindices[species]]
        elif MW[species][1] == 'H2O':
            lumped[:, 6] += m[:, speciesindices[species]]
        elif MW[species][1] == 'char':
            lumped[:, 7] += m[:, speciesindices[species]]
        else:
            print '%s does not have a phase defined.' % species

    # Make a more lumped (3 component) model
    morelumped = np.zeros((m.shape[0], 3))
    morelumped[:, 0] = lumped[:, 0] + lumped[:, 7]
    morelumped[:, 1] = lumped[:, 1] + lumped[:, 2] + lumped[:, 6]
    morelumped[:, 2] = lumped[:, 3] + lumped[:, 4] + lumped[:, 5]

    return lumped, phenolic_families, morelumped


def generate_report(speciesindices, specieslist, y, m, t, which_result):
    """
    Print a descriptive summary of a specific simulation.

    Parameters
    ----------
    speciesindices : dict
                     dictionary from `load_results()` where species names are
                     keys and values are the index in `y` that corresponds to
                     that species
    specieslist    : list
                     the specieslist_ddasac object from load_results()
    y              : numpy array
                     a matrix with the concentrations of each species in the
                     kinetic scheme for every time in `t` (mol/L)
    m              : numpy array
                     a matrix with the mass fraction of each species in the
                     kinetic scheme for every time in `t`
    t              : numpy array
                     array with all the times (s) corresponding to entries in
                     `y` and `T`
    which_result   : str
                     the name of the simulation folder you are analysing

    Returns
    -------
    None
    """
    (ea0, ea, ea0_molpercent, ea_molpercent, ea0_wtpercent, ea_wtpercent, choice,
     t_index) = tar_elem_analysis(speciesindices, y, t)

    # Header and elemental analysis results
    print1 = ('\n{:-^80}\n'
              'Analysis of folder: {}\n'
              '{}\n'
              '\n{:.^80}\n\n'
              'Feedstock (wt%)  : {:.1%} C {:>7.1%} H {:>7.1%} O\n'
              'Bio-oil (wt%)    : {:.1%} C {:>7.1%} H {:>7.1%} O\n\n'
              'Feedstock (mol%) : {:.1%} C {:>7.1%} H {:>7.1%} O\n'
              'Bio-oil (mol%)   : {:.1%} C {:>7.1%} H {:>7.1%} O\n'
              .format(' REPORT ', which_result.value, choice,
                      ' Elemental Analysis ', ea0_wtpercent[0], ea0_wtpercent[1],
                      ea0_wtpercent[2], ea_wtpercent[0], ea_wtpercent[1],
                      ea_wtpercent[2], ea0_molpercent[0], ea0_molpercent[1],
                      ea0_molpercent[2], ea_molpercent[0], ea_molpercent[1],
                      ea_molpercent[2]))

    # H:C ratio in tar
    # a low H:C ratio limits hydrocarbon yield during upgrading, so upgraded
    # product is primarily aromatics. Combustion energetics can be estimated from
    # the bond energies for all the classifications of fossil fuels. The amount of
    # energy released is dependent on the oxidation state of the carbons in the
    # hydrocarbon which is related to the hydrogen/carbon ratio.  The more hydrogen
    # per carbon, the lower the oxidation state and the more energy that will be
    # released during the oxidation reaction.  Thus the greater the H/C ratio,
    # the more energy release on combustion.
    # Sample values: gas 4/1, petroleum 2/1, coal 1/1, ethanol 3/1
    print2 = '\nH:C ratio of tar = {:.3}\n'.format(ea[1] / ea[0])

    # Moisture content in tar -- typical value for wood bio-oil is 25%
    mtot = [0]
    for species in MW:
        if MW[species][1] in set(['t', 'lt', 'H2O']):
            # the total mass fraction of all tar components at the specified time
            mtot += m[t_index, speciesindices[species]]
    # The moisture content (wt%) in the bio-oil
    mc = m[t_index, speciesindices['H2O']] / mtot
    print3 = '\nMoisture content of tar (wt%) = {:.1%}\n'.format(mc[0])

    # The distribution of carbon functional groups in the tar
    groups = ['C=O', 'aromatic C-O', 'aromatic C-C', 'aromatic C-H',
              'aliphatic C-O', 'aromatic Methoxyl', 'aliphatic C-C']
    Cfun0 = C_fun_gen(['initial'], speciesindices, y, 0)
    Cfun = C_fun_gen(['t','lt'], speciesindices, y, t_index)
    Cfunheavy = C_fun_gen(['t'], speciesindices, y, t_index)
    Cfunlight = C_fun_gen(['lt'], speciesindices, y, t_index)
    print4 = ('\n{:.^80}\n\n'
              '{: <19}{: <16}{: <16}{: <16}{: <16}'
              .format(' Distribution of C-functional groups (shown as % of C) ',
                      ' ','Feedstock','Bio-oil','Heavy oil','Light oil'))

    print print1, print2, print3, print4
    for i, group in enumerate(groups):
        print5 = ('%s%s%s%s%s' % ('{: <19}'.format(group),
                                  '{: <16.2%}'.format(Cfun0[i]),
                                  '{: <16.2%}'.format(Cfun[i]),
                                  '{: <16.2%}'.format(Cfunheavy[i]),
                                  '{: <16.2%}'.format(Cfunlight[i])))
        print print5

    # lump the molecules in the model into groups
    lumped, phenolic_families, morelumped = lump_species(speciesindices, m)
    # The final mass fractions of each component (morelumped)
    print6 = ('\n{:.^80}\n\n'
              'Solids:\t\t {:>10.2%}\n'
              'Gases:\t\t {:>10.2%}\n'
              'Total Tar:\t {:>10.2%}\n'
              '  Heavy Tars:\t {:>10.2%}\n'
              '  Light Tars:\t {:>10.2%}\n'
              '  Water:\t {:>10.2%}'
              .format(' Final lumped product yields (wt%) ', morelumped[-1, 0],
                      morelumped[-1, 2], morelumped[-1, 1], lumped[-1, 1],
                      lumped[-1, 2], lumped[-1, 6]))
    print7 = ('\n\n{:.2%} of heavy tars are derived from phenol, '
              '{:.2%} are derived from syringol'
              .format(phenolic_families[-1, 0] / lumped[-1, 1],
                      phenolic_families[-1, 1] / lumped[-1, 1]))

    # Look at the final distribution of gases
    print8 = '\n\n{:.^80}\n'.format(' Final gas composition (wt%) ')
    print print6, print7, print8
    # dictionary with the ending mass fraction for each species
    final_mass_fracs = {}
    for species in specieslist:
        final_mass_fracs[species] = m[t_index, speciesindices[species]]
    gas_list = {}
    for species in specieslist:
        if MW[species][1] in ('g', 'CO', 'CO2'):
            gas_list[species] = final_mass_fracs[species]
    gas_w = sorted(gas_list, key=gas_list.__getitem__, reverse=True)[:8]
    for species in gas_w:
        print9 = ('%s\t%s' % ('{0: <8}'.format(species),
                              '{0: <18}'.format(final_mass_fracs[species])))
        print print9

    # identify the 20 species with the highest mass fractions at the end
    print10 = ('\n{:.^80}\n'
               .format(' Top 20 species (by mass fraction) at end (wt%) '))
    print print10
    top = sorted(final_mass_fracs, key=final_mass_fracs.__getitem__,
                 reverse=True)[:20]
    for species in top:
        print11 = '%s\t%s' % ('{0: <8}'.format(species),
                              '{0: <18}'.format(final_mass_fracs[species]))
        print print11